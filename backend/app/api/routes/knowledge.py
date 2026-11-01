"""Rotas de knowledge — base de fatos (Fase 4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.data.errors import DataError
from app.database import get_session
from app.database.models import KnowledgeFact
from app.schemas.knowledge import CreateFact, FactList, FactOut
from app.services.knowledge import create_fact, delete_fact, get_fact, list_facts

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/", response_model=FactOut, status_code=201)
def create(payload: CreateFact, session: Session = Depends(get_session)) -> FactOut:
    # unicidade de key
    from sqlalchemy import select

    existing = session.scalar(select(KnowledgeFact).where(KnowledgeFact.key == payload.key))
    if existing is not None:
        raise DataError(f"fact com key '{payload.key}' já existe")
    row = create_fact(session, payload)
    return _to_out(row)


@router.get("/search", response_model=FactList)
def search(q: str = Query(...), session: Session = Depends(get_session)) -> FactList:
    # substring em key
    items = list_facts(session, key=q)
    return FactList(items=[_to_out(r) for r in items], total=len(items))


@router.get("/", response_model=FactList)
def list_all(tag: str | None = None, session: Session = Depends(get_session)) -> FactList:
    items = list_facts(session, tag=tag)
    return FactList(items=[_to_out(r) for r in items], total=len(items))


@router.get("/{fact_id}", response_model=FactOut)
def detail(fact_id: str, session: Session = Depends(get_session)) -> FactOut:
    try:
        parsed = uuid.UUID(fact_id)
    except ValueError as exc:
        raise NotFoundError(f"fact '{fact_id}' não encontrado") from exc
    row = get_fact(session, parsed)
    if row is None:
        raise NotFoundError(f"fact '{fact_id}' não encontrado")
    return _to_out(row)


@router.delete("/{fact_id}", status_code=204)
def delete(fact_id: str, session: Session = Depends(get_session)):
    try:
        parsed = uuid.UUID(fact_id)
    except ValueError as exc:
        raise NotFoundError(f"fact '{fact_id}' não encontrado") from exc
    if not delete_fact(session, parsed):
        raise NotFoundError(f"fact '{fact_id}' não encontrado")
    return None


def _to_out(row: KnowledgeFact) -> FactOut:
    return FactOut(
        id=row.id,
        key=row.key,
        value=row.value,
        tags=row.tags or [],
        source=row.source,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
