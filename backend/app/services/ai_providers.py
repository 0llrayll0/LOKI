from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import decrypt_secret, encrypt_secret, mask_secret
from app.database.models import AiProvider, AiProviderUsage
from app.providers.llm.openai_compat import OpenAICompatProvider
from app.schemas.ai_providers import AIProviderCreate, AIProviderUpdate


def _adapter(row: AiProvider) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name=row.name,
        base_url=row.base_url,
        api_key=decrypt_secret(row.api_key_encrypted),
        model=row.default_model,
        timeout=int((row.config or {}).get("timeout", 10)),
    )




def record_usage(
    session: Session,
    row: AiProvider | None,
    *,
    operation: str,
    status: str,
    latency_ms: float | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    error: str | None = None,
    model: str | None = None,
):
    entry = AiProviderUsage(
        provider_id=row.id if row else None,
        provider_name=row.name if row else "unknown",
        model=model or (row.default_model if row else None),
        operation=operation,
        status=status,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        error=error,
        created_at=datetime.now(UTC),
    )
    session.add(entry)
    session.commit()
    return entry

def _to_out(row: AiProvider):
    from app.schemas.ai_providers import AIProviderOut

    key = decrypt_secret(row.api_key_encrypted)
    return AIProviderOut(
        id=row.id,
        name=row.name,
        type=row.type,
        base_url=row.base_url,
        default_model=row.default_model,
        has_key=bool(key),
        api_key_masked=mask_secret(key),
        enabled=row.enabled,
        is_default=row.is_default,
        config=row.config or {},
        last_tested_at=row.last_tested_at,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_providers(session: Session) -> list[AiProvider]:
    return list(session.scalars(select(AiProvider).order_by(AiProvider.created_at.desc())).all())


def get_provider(session: Session, provider_id: uuid.UUID) -> AiProvider | None:
    return session.get(AiProvider, provider_id)


def create_provider(session: Session, payload: AIProviderCreate) -> AiProvider:
    now = datetime.now(UTC)
    row = AiProvider(
        name=payload.name.strip(),
        type=payload.type,
        base_url=payload.base_url.strip(),
        default_model=payload.default_model,
        api_key_encrypted=encrypt_secret(payload.api_key),
        enabled=payload.enabled,
        is_default=payload.is_default,
        config=payload.config or {},
        created_at=now,
        updated_at=now,
    )
    # ensure single default
    if row.is_default:
        for r in list_providers(session):
            r.is_default = False
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_provider(session: Session, row: AiProvider, payload: AIProviderUpdate) -> AiProvider:
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.type is not None:
        row.type = payload.type
    if payload.base_url is not None:
        row.base_url = payload.base_url.strip()
    if "default_model" in (payload.model_fields_set or set()):
        row.default_model = payload.default_model
    if "api_key" in (payload.model_fields_set or set()):
        row.api_key_encrypted = encrypt_secret(payload.api_key)
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.is_default is not None:
        if payload.is_default:
            for r in list_providers(session):
                if r.id != row.id:
                    r.is_default = False
        row.is_default = payload.is_default
    if payload.config is not None:
        row.config = payload.config
    row.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return row


def delete_provider(session: Session, row: AiProvider) -> None:
    session.delete(row)
    session.commit()


def test_provider(session: Session, row: AiProvider) -> tuple[bool, str | None, list[str]]:
    import time
    adapter = _adapter(row)
    started = time.perf_counter()
    ok, err = adapter.validate_credentials()
    models = adapter.list_models() if ok else []
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    row.last_tested_at = datetime.now(UTC)
    row.last_error = None if ok else err
    row.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    record_usage(
        session,
        row,
        operation="health_check",
        status="ok" if ok else "error",
        latency_ms=latency_ms,
        error=err,
        model=row.default_model,
    )
    return ok, err, models


def list_models(session: Session, row: AiProvider) -> list[str]:
    return _adapter(row).list_models()


def to_out(row: AiProvider):
    return _to_out(row)


def list_usage(session: Session, provider_id: uuid.UUID | None = None, limit: int = 100) -> list[AiProviderUsage]:
    from sqlalchemy import select as _select

    from app.database.models import AiProviderUsage as U

    stmt = _select(U).order_by(U.created_at.desc()).limit(limit)
    if provider_id is not None:
        stmt = stmt.where(U.provider_id == provider_id)
    return list(session.scalars(stmt).all())
