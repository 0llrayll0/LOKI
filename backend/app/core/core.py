"""Fachada LOKI CORE (singleton)."""

from __future__ import annotations

import threading

from app.core.events import EventBus
from app.core.providers import ProviderRegistry
from app.core.scheduler import Scheduler


class LokiCore:
    def __init__(self) -> None:
        self.providers = ProviderRegistry()
        self.events = EventBus()
        self.scheduler = Scheduler()

    def register_provider(self, name: str, provider: object) -> None:
        self.providers.register(name, provider)

    def emit(self, event: str, payload=None) -> list:
        return self.events.emit(event, payload)

    def on(self, event: str, handler) -> None:
        self.events.on(event, handler)


_core: LokiCore | None = None
_lock = threading.Lock()


def get_core() -> LokiCore:
    global _core
    if _core is None:
        with _lock:
            if _core is None:
                _core = LokiCore()
    return _core


def register_provider(name: str, provider: object) -> None:
    get_core().register_provider(name, provider)


def emit(event: str, payload=None) -> list:
    return get_core().emit(event, payload)


def on(event: str, handler) -> None:
    get_core().on(event, handler)