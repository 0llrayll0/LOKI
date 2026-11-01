from __future__ import annotations

import uuid
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AIProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=512)
    default_model: str | None = Field(default=None, max_length=255)
    api_key: str | None = None
    enabled: bool = True
    is_default: bool = False
    config: dict = Field(default_factory=dict)


class AIProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    default_model: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None
    config: dict | None = None


class AIProviderOut(BaseModel):
    id: UUID
    name: str
    type: str
    base_url: str
    default_model: str | None
    has_key: bool
    api_key_masked: str
    enabled: bool
    is_default: bool
    config: dict
    last_tested_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class TestResult(BaseModel):
    ok: bool
    message: str | None = None
    models: list[str] = Field(default_factory=list)


class ModelsOut(BaseModel):
    models: list[str] = Field(default_factory=list)


class UsageOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID | None
    provider_name: str
    model: str | None
    operation: str
    status: str
    latency_ms: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    error: str | None
    created_at: datetime


class AIProviderDiscover(BaseModel):
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str | None = None
