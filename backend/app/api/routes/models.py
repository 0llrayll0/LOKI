from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.ai_providers import resolve_provider_config, update_provider_config

router = APIRouter(prefix="/api/models", tags=["models"])

_STATE = {"mode": "api", "model": "default"}


class SelectorBody(BaseModel):
    mode: str | None = None
    model: str | None = None


@router.get("/selector")
def get_selector():
    cfg = resolve_provider_config()
    return {
        "mode": _STATE["mode"],
        "model": cfg.get("model") or _STATE["model"],
        "provider": cfg.get("provider"),
    }


@router.post("/selector")
def set_selector(body: SelectorBody):
    if body.mode is not None:
        if body.mode not in ("api", "local"):
            raise HTTPException(status_code=400, detail="mode deve ser api ou local")
        _STATE["mode"] = body.mode
    if body.model is not None:
        _STATE["model"] = body.model
        try:
            update_provider_config(model=body.model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    cfg = resolve_provider_config()
    return {
        "mode": _STATE["mode"],
        "model": cfg.get("model") or _STATE["model"],
        "provider": cfg.get("provider"),
    }
