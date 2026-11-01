"""Provider Hub — gerenciamento de provedores de IA."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.database import get_session
from app.schemas.ai_providers import (
    AIProviderCreate,
    AIProviderDiscover,
    AIProviderOut,
    AIProviderUpdate,
    ModelsOut,
    TestResult,
    UsageOut,
)
from app.services.ai_providers import (
    create_provider,
    delete_provider,
    get_provider,
    list_models,
    list_providers,
    list_usage,
    test_provider,
    to_out,
    update_provider,
)

router = APIRouter(prefix="/api/ai/providers", tags=["ai-providers"])
SessionDep = None


def _session_dep(session: Session = Depends(get_session)):
    return session


def _parse_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise NotFoundError(f"provider '{value}' não encontrado") from exc


@router.get("/", response_model=list[AIProviderOut])
def list_all(session: Session = Depends(get_session)):
    return [to_out(r) for r in list_providers(session)]


@router.post("/", response_model=AIProviderOut, status_code=201)
def create(payload: AIProviderCreate, session: Session = Depends(get_session)):
    row = create_provider(session, payload)
    return to_out(row)


@router.get("/{provider_id}", response_model=AIProviderOut)
def detail(provider_id: str, session: Session = Depends(get_session)):
    row = get_provider(session, _parse_id(provider_id))
    if row is None:
        raise NotFoundError(f"provider '{provider_id}' não encontrado")
    return to_out(row)


@router.patch("/{provider_id}", response_model=AIProviderOut)
def update(provider_id: str, payload: AIProviderUpdate, session: Session = Depends(get_session)):
    row = get_provider(session, _parse_id(provider_id))
    if row is None:
        raise NotFoundError(f"provider '{provider_id}' não encontrado")
    row = update_provider(session, row, payload)
    return to_out(row)


@router.delete("/{provider_id}", status_code=204)
def delete(provider_id: str, session: Session = Depends(get_session)):
    row = get_provider(session, _parse_id(provider_id))
    if row is None:
        raise NotFoundError(f"provider '{provider_id}' não encontrado")
    delete_provider(session, row)
    return None


@router.post("/{provider_id}/test", response_model=TestResult)
def test(provider_id: str, session: Session = Depends(get_session)):
    row = get_provider(session, _parse_id(provider_id))
    if row is None:
        raise NotFoundError(f"provider '{provider_id}' não encontrado")
    ok, err, models = test_provider(session, row)
    return TestResult(ok=ok, message=err, models=models)


@router.post("/discover")
def discover(payload: AIProviderDiscover):
    from app.providers.llm.openai_compat import OpenAICompatProvider

    adapter = OpenAICompatProvider(
        name="discover",
        base_url=payload.base_url.strip(),
        api_key=payload.api_key,
    )
    models = adapter.list_models()
    ok, err = adapter.validate_credentials() if not models else (True, None)
    return TestResult(ok=ok or bool(models), message=err, models=models)


@router.get("/{provider_id}/models", response_model=ModelsOut)
def models(provider_id: str, session: Session = Depends(get_session)):
    row = get_provider(session, _parse_id(provider_id))
    if row is None:
        raise NotFoundError(f"provider '{provider_id}' não encontrado")
    try:
        ms = list_models(session, row)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return ModelsOut(models=ms)




@router.get("/usage", response_model=list[UsageOut])
def usage_all(limit: int = 100, session: Session = Depends(get_session)):
    rows = list_usage(session, None, limit=limit)
    return [UsageOut.model_validate(r) for r in rows]


@router.get("/{provider_id}/usage", response_model=list[UsageOut])
def usage_for(provider_id: str, limit: int = 100, session: Session = Depends(get_session)):
    row = get_provider(session, _parse_id(provider_id))
    if row is None:
        raise NotFoundError(f"provider '{provider_id}' não encontrado")
    rows = list_usage(session, row.id, limit=limit)
    return [UsageOut.model_validate(r) for r in rows]
