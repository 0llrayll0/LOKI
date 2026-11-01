"""Fase 8 — cenários (mutations + recálculo)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from app.prediction import predict


@dataclass
class ScenarioResult:
    forecast: list[float]
    lower: list[float]
    upper: list[float]
    metrics: dict[str, float]

    def to_dict(self):
        return asdict(self)


def simulate(
    values: Sequence[float],
    mutations: list[dict],
    horizon: int = 7,
    method: str = "naive",
) -> ScenarioResult:
    series = list(values)
    for m in mutations:
        op = m.get("op")
        if op == "add":
            series.append(float(m.get("value", 0.0)))
        elif op == "scale":
            factor = float(m.get("factor", 1.0))
            series = [x * factor for x in series]
        elif op == "replace_last":
            if series:
                series[-1] = float(m.get("value", series[-1]))
    res = predict(series, horizon=horizon, method=method)  # type: ignore
    return ScenarioResult(
        forecast=res.forecast,
        lower=res.lower,
        upper=res.upper,
        metrics=res.metrics,
    )
