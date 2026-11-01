"""Fase 7 — detecção de anomalias (z-score / IQR)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class PatternResult:
    indices: list[int]
    scores: list[float]
    method: str

    def to_dict(self):
        return asdict(self)


def detect(
    values,
    method="zscore",
    threshold=3.0,
):
    arr = np.asarray(values, dtype=float).ravel()
    n = arr.size
    if n == 0:
        return PatternResult(indices=[], scores=[], method=method)
    if method == "zscore":
        mu = float(np.mean(arr))
        sd = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        scores = [float((x - mu) / sd) if sd else 0.0 for x in arr]
        indices = [i for i, s in enumerate(scores) if abs(s) >= threshold]
    elif method == "iqr":
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        lo = q1 - 1.5 * iqr
        hi = q3 + 1.5 * iqr
        scores = [float(x) for x in arr]
        indices = [i for i, x in enumerate(arr) if x < lo or x > hi]
    else:
        raise ValueError(f"método desconhecido: {method}")
    return PatternResult(indices=indices, scores=scores, method=method)
