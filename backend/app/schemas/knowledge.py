"""Schemas Pydantic das rotas de knowledge (Fase 4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateFact(BaseModel):
    key: str
    value: Any
    tags: list[str] = Field(default_factory=list)
    source: str | None = None


class FactOut(BaseModel):
    id: uuid.UUID
    key: str
    value: Any
    tags: list[str]
    source: str | None = None
    created_at: datetime
    updated_at: datetime


class FactList(BaseModel):
    items: list[FactOut]
    total: int
