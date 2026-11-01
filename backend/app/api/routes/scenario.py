from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.scenario import simulate

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


class ScenarioIn(BaseModel):
    values: list[float]
    mutations: list[dict] = []
    horizon: int = 7
    method: str = "naive"


@router.post("/simulate")
def simulate_route(payload: ScenarioIn):
    res = simulate(
        payload.values, payload.mutations,
        horizon=payload.horizon, method=payload.method,
    )
    return res.to_dict()
