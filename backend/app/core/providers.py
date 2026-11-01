"""Registry de provedores do LOKI CORE."""

from __future__ import annotations


class DuplicateProviderError(Exception):
    """Levantado ao registrar um provedor com nome já existente."""


class ProviderRegistry:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def register(self, name: str, provider: object) -> None:
        if name in self._items:
            raise DuplicateProviderError(f"provider already registered: {name}")
        self._items[name] = provider

    def get(self, name: str) -> object:
        if name not in self._items:
            raise KeyError(name)
        return self._items[name]

    def list_names(self) -> list[str]:
        return list(self._items.keys())

    def unregister(self, name: str) -> None:
        self._items.pop(name, None)

    def __contains__(self, name: object) -> bool:
        return name in self._items