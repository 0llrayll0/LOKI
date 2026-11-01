"""Contratos de provedores de LLM."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    base_url: str
    model: str | None

    def list_models(self) -> list[str]: ...
    def health_check(self) -> tuple[bool, str | None]: ...
    def validate_credentials(self) -> tuple[bool, str | None]: ...
    def generate(self, prompt: str, *, max_tokens: int = 256) -> str: ...
