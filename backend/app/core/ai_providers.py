"""Provedores de IA no padrão Pandora (config por env + runtime in-memory)."""

from __future__ import annotations

import os
from typing import Any

AI_PROVIDERS = ["ollama", "openai", "custom", "anthropic", "gemini"]

_DEFAULTS = {
    "provider": os.getenv("LOKI_AI_PROVIDER", "ollama"),
    "base_url": os.getenv("LOKI_AI_BASE_URL", "http://localhost:11434"),
    "model": os.getenv("LOKI_AI_MODEL", ""),
    "api_key": os.getenv("LOKI_AI_API_KEY", ""),
}

_RUNTIME: dict[str, Any] = {}


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:3]}...{key[-4:]}"


def resolve_provider_config() -> dict[str, Any]:
    cfg = dict(_DEFAULTS)
    cfg.update({k: v for k, v in _RUNTIME.items() if v is not None})
    if cfg.get("provider") not in AI_PROVIDERS:
        cfg["provider"] = (
            _DEFAULTS["provider"] if _DEFAULTS["provider"] in AI_PROVIDERS else "ollama"
        )
    return cfg


def update_provider_config(
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    if provider is not None:
        if provider not in AI_PROVIDERS:
            raise ValueError(f"provider inválido: {provider}")
        _RUNTIME["provider"] = provider
    if base_url is not None:
        _RUNTIME["base_url"] = base_url
    if model is not None:
        _RUNTIME["model"] = model
    if api_key is not None:
        _RUNTIME["api_key"] = api_key
    return resolve_provider_config()


def config_public(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or resolve_provider_config()
    key = cfg.get("api_key") or ""
    return {
        "provider": cfg.get("provider"),
        "base_url": cfg.get("base_url"),
        "model": cfg.get("model"),
        "has_key": bool(key),
        "api_key_masked": _mask(key),
    }
