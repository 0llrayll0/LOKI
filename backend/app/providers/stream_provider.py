"""Fase 9 — StreamProvider (Redis Streams) com fallback em memória."""

from __future__ import annotations

from collections import defaultdict, deque

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


class StreamProvider:
    def __init__(self, url: str | None = None, client=None):
        self.client = client
        if self.client is None and redis is not None and url:
            try:
                self.client = redis.from_url(url)
                self.client.ping()
            except Exception:
                self.client = None
        self._memory: dict[str, deque] = defaultdict(deque)

    def publish(self, stream: str, payload: dict) -> str:
        if self.client is not None:
            try:
                return self.client.xadd(stream, {k: str(v) for k, v in payload.items()})
            except Exception:
                pass
        eid = str(len(self._memory[stream]))
        self._memory[stream].append((eid, payload))
        return eid

    def read(self, stream: str, count: int = 10) -> list[dict]:
        if self.client is not None:
            try:
                res = self.client.xread({stream: "0"}, count=count)
                out = []
                for _, entries in res:
                    for eid, data in entries:
                        out.append({
                            "id": eid,
                            **{
                                k: (v.decode() if isinstance(v, bytes) else v)
                                for k, v in data.items()
                            },
                        })
                return out
            except Exception:
                pass
        out = []
        for eid, payload in list(self._memory[stream])[-count:]:
            out.append({"id": eid, **payload})
        return out
