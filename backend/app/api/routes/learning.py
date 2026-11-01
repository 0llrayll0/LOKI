from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.learning import record_outcome, trigger_retrain

router = APIRouter(prefix="/api/learning", tags=["learning"])
SessionDep = None


@router.post("/outcome")
def outcome(payload: dict, session: Session = Depends(get_session)):
    record_outcome(
        session,
        payload.get("model", ""),
        payload.get("event", ""),
        float(payload.get("actual", 0.0)),
    )
    return {"status": "recorded"}


@router.post("/retrain")
def retrain(payload: dict, session: Session = Depends(get_session)):
    return trigger_retrain(session, payload.get("model", ""))
