"""Event bus do LOKI CORE (local + Redis Streams quando disponível)."""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict, deque
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


class EventBus:
    def __init__(self, redis_url: str | None = None, client=None) -> None:
        self._handlers: dict[str, list] = defaultdict(list)
        self.client = client
        if self.client is None and redis is not None and (redis_url or os.getenv("REDIS_URL")):
            try:
                self.client = redis.from_url(redis_url or os.getenv("REDIS_URL"))
                self.client.ping()
            except Exception:
                self.client = None
        self._memory: dict[str, deque] = defaultdict(deque)

    def on(self, event: str, handler) -> None:
        self._handlers[event].append(handler)

    def off(self, event: str, handler) -> None:
        try:
            self._handlers[event].remove(handler)
        except (ValueError, KeyError):
            pass

    def emit(self, event: str, payload=None) -> list:
        results = []
        for handler in list(self._handlers.get(event, [])):
            try:
                results.append(handler(payload))
            except Exception as exc:  # noqa: BLE001
                logger.exception("event_handler_error", extra={"event": event})
                results.append(exc)
        # real-ish bus: Redis Streams
        try:
            if self.client is not None:
                ts = datetime.now(UTC).isoformat()
                body = {"payload": json.dumps(payload, default=str), "ts": ts}
                self.client.xadd(f"loki:events:{event}", body)
            else:
                self._memory[event].append(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("event_publish_failed", extra={"event": event, "error": str(exc)})
        return results
