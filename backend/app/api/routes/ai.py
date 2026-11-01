from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.ai_providers import (
    AI_PROVIDERS,
    config_public,
    resolve_provider_config,
    update_provider_config,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AIConfigBody(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


@router.get("/config")
def get_config():
    return config_public()


@router.put("/config")
def put_config(body: AIConfigBody):
    try:
        cfg = update_provider_config(
            provider=body.provider,
            base_url=body.base_url,
            model=body.model,
            api_key=body.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return config_public(cfg)


@router.post("/run")
def run_ai(body: dict | None = None):
    cfg = resolve_provider_config()
    # placeholder seguro: nunca falha; heurística simples
    prompt = ""
    if isinstance(body, dict):
        prompt = str(body.get("prompt") or "")
    return {
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "result": "heuristic",
        "echo": prompt[:200],
    }


__all__ = ["AI_PROVIDERS"]
