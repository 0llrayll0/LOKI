from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.providers.stream_provider import StreamProvider

router = APIRouter(prefix="/api/stream", tags=["stream"])
_provider = StreamProvider()


class PubIn(BaseModel):
    stream: str
    payload: dict


@router.post("/publish")
def publish(payload: PubIn):
    return {"id": _provider.publish(payload.stream, payload.payload)}


@router.get("/read")
def read(stream: str, count: int = 10):
    return {"items": _provider.read(stream, count=count)}
