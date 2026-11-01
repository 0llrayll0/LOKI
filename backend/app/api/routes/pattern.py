from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.pattern import detect

router = APIRouter(prefix="/api/pattern", tags=["pattern"])


class PatternIn(BaseModel):
    values: list[float]
    method: str = "zscore"
    threshold: float = 3.0


@router.post("/detect")
def detect_route(payload: PatternIn):
    r = detect(payload.values, method=payload.method, threshold=payload.threshold)
    return r.to_dict()
