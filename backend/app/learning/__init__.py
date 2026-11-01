"""Fase 8 — learning (record outcome / retrain stub)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.knowledge import CreateFact
from app.services.knowledge import create_fact


def record_outcome(session: Session, model: str, event: str, actual: float) -> None:
    payload = CreateFact(
        key=f"outcome:{model}:{event}",
        value={"model": model, "event": event, "actual": actual},
        tags=["learning", "outcome"],
        source="learning",
    )
    create_fact(session, payload)


def trigger_retrain(session: Session, model: str) -> dict:
    payload = CreateFact(
        key=f"retrain:{model}",
        value={"model": model, "status": "requested"},
        tags=["learning", "retrain"],
        source="learning",
    )
    create_fact(session, payload)
    return {"model": model, "status": "requested"}
