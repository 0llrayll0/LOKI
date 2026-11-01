import json
import urllib.request
from datetime import datetime

from app.providers.base import Observation


class ApiProvider:
    def __init__(self, name: str, url: str, headers=None, timeout: int = 10) -> None:
        self.name = name
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout

    def fetch(self) -> list[Observation]:
        req = urllib.request.Request(self.url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        records = data if isinstance(data, list) else [data]
        now = datetime.now()
        out = []
        for r in records:
            payload = r if isinstance(r, dict) else {"value": r}
            out.append(Observation(source=self.url, observed_at=now, payload=payload))
        return out