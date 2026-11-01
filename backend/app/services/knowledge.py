"""Serviço de knowledge facts (Fase 4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import KnowledgeFact
from app.schemas.knowledge import CreateFact


def create_fact(session: Session, payload: CreateFact) -> KnowledgeFact:
    now = datetime.now(UTC)
    row = KnowledgeFact(
        key=payload.key,
        value=payload.value,
        tags=list(payload.tags or []),
        source=payload.source,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_fact(session: Session, fact_id: uuid.UUID) -> KnowledgeFact | None:
    return session.get(KnowledgeFact, fact_id)


def list_facts(
    session: Session, tag: str | None = None, key: str | None = None
) -> list[KnowledgeFact]:
    stmt = select(KnowledgeFact)
    if tag:
        # tags é JSON list; filtra carregando todos e filtrando em Python (sem deps)
        rows = session.scalars(stmt).all()
        return [r for r in rows if tag in (r.tags or [])]
    if key:
        rows = session.scalars(stmt).all()
        return [r for r in rows if key.lower() in r.key.lower()]
    return list(session.scalars(stmt).all())


def delete_fact(session: Session, fact_id: uuid.UUID) -> bool:
    row = session.get(KnowledgeFact, fact_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True
