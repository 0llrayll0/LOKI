"""Fase 7 — risco (agregação probabilidades/impactos)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass


@dataclass
class RiskResult:
    score: int
    level: str
    components: dict

    def to_dict(self):
        return asdict(self)


def assess(items: Sequence[dict]) -> RiskResult:
    # items: list of {probability, impact} (0..1 or 0..100)
    total = 0.0
    for it in items:
        p = float(it.get("probability", 0.0))
        imp = float(it.get("impact", 0.0))
        if p > 1:
            p = p / 100.0
        if imp > 1:
            imp = imp / 100.0
        total += p * imp
    # normalize
    n = max(1, len(items))
    raw = (total / n) * 100.0
    score = int(round(min(100.0, max(0.0, raw * (1 + 0.1 * (n - 1))))))
    score = min(100, max(0, score))
    if score < 33:
        level = "low"
    elif score < 66:
        level = "medium"
    else:
        level = "high"
    return RiskResult(score=score, level=level, components={"count": n, "raw": raw})
