from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.risk import assess

router = APIRouter(prefix="/api/risk", tags=["risk"])


class RiskIn(BaseModel):
    items: list[dict]


@router.post("/assess")
def assess_route(payload: RiskIn):
    return assess(payload.items).to_dict()
