"""Provider de arquivos batch (CSV/JSON)."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from app.providers.base import Observation


def _records_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _records_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("JSON deve conter lista ou objeto")


class BatchProvider:
    def __init__(self, name: str, path: str | Path) -> None:
        self.name = name
        self.path = Path(path)

    def fetch(self) -> list[Observation]:
        if not self.path.exists():
            raise FileNotFoundError(f"arquivo não encontrado: {self.path}")
        ext = self.path.suffix.lower()
        if ext == ".csv":
            rows = _records_csv(self.path)
        elif ext == ".json":
            rows = _records_json(self.path)
        else:
            raise ValueError(f"formato não suportado: {ext}")
        now = datetime.now()
        out = []
        for r in rows:
            payload = r if isinstance(r, dict) else {"value": r}
            out.append(Observation(source=str(self.path), observed_at=now, payload=payload))
        return out