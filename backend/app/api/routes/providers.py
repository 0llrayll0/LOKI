from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.core import get_core
from app.core.errors import NotFoundError
from app.providers.base import Observation

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("/")
def list_providers():
    return {"providers": get_core().providers.list_names()}


@router.post("/{name}/fetch")
def fetch_provider(name: str):
    core = get_core()
    try:
        provider = core.providers.get(name)
    except KeyError as exc:
        raise NotFoundError(f"provider '{name}' não registrado") from exc
    try:
        obs: list[Observation] = provider.fetch()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    items = [o.payload for o in obs[:10]]
    return {"name": name, "count": len(obs), "items": items}