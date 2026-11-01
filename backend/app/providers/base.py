"""Base de providers (observações)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class Observation:
    source: str
    observed_at: datetime
    payload: dict = field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    name: str

    def fetch(self) -> list[Observation]: ...