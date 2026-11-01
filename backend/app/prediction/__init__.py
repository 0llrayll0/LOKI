"""Fase 6 — baseline de previsão (sem novas dependências)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd

Method = Literal["naive", "seasonal_naive", "moving_average"]


@dataclass
class PredictionResult:
    method: str
    horizon: int
    forecast: list[float]
    lower: list[float]
    upper: list[float]
    metrics: dict[str, float]
    residual_std: float

    def to_dict(self) -> dict:
        return asdict(self)


def _to_series(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError("série vazia")
    if np.isnan(arr).any():
        s = pd.Series(arr)
        s = s.interpolate(limit_direction="both").ffill().bfill()
        arr = s.to_numpy(dtype=float)
    return arr


def _period_for_method(
    arr: np.ndarray,
    method: Method,
    seasonal_period: int | None,
    window: int | None,
) -> tuple[int, int]:
    n = arr.size
    if method == "seasonal_naive":
        p = seasonal_period or (7 if n >= 14 else max(1, n // 2))
        p = max(1, min(p, n))
    else:
        p = 1
    if method == "moving_average":
        w = window or min(7, n)
        w = max(1, min(w, n))
    else:
        w = 1
    return p, w


def _residuals(arr: np.ndarray, method: Method, seasonal_period: int, window: int) -> np.ndarray:
    n = arr.size
    preds = np.full(n, np.nan)
    for i in range(n):
        if method == "naive":
            if i == 0:
                continue
            preds[i] = arr[i - 1]
        elif method == "seasonal_naive":
            if i - seasonal_period < 0:
                continue
            preds[i] = arr[i - seasonal_period]
        elif method == "moving_average":
            start = max(0, i - window)
            if start >= i:
                continue
            preds[i] = arr[start:i].mean()
    mask = ~np.isnan(preds)
    return arr[mask] - preds[mask]


def _mape(arr, method, sp, w):
    n = arr.size
    preds = np.full(n, np.nan)
    for i in range(n):
        if method == "naive":
            if i == 0:
                continue
            preds[i] = arr[i - 1]
        elif method == "seasonal_naive":
            if i - sp < 0:
                continue
            preds[i] = arr[i - sp]
        elif method == "moving_average":
            start = max(0, i - w)
            if start >= i:
                continue
            preds[i] = arr[start:i].mean()
    mask = ~np.isnan(preds)
    actual = arr[mask]
    pred = preds[mask]
    nz = actual != 0
    if nz.sum() == 0:
        return 0.0
    return float(np.mean(np.abs((actual[nz] - pred[nz]) / actual[nz])) * 100)


def predict(
    values: Sequence[float],
    horizon: int = 7,
    method: Method = "naive",
    seasonal_period: int | None = None,
    window: int | None = None,
    z: float = 1.96,
) -> PredictionResult:
    if horizon < 1:
        raise ValueError("horizon deve ser >= 1")
    if method not in ("naive", "seasonal_naive", "moving_average"):
        raise ValueError(f"método desconhecido: {method}")
    arr = _to_series(values)
    sp, w = _period_for_method(arr, method, seasonal_period, window)
    resid = _residuals(arr, method, sp, w)
    resid_std = float(np.std(resid, ddof=1)) if resid.size > 1 else 0.0
    if resid.size == 0 or math.isnan(resid_std):
        resid_std = 0.0

    fc: list[float] = []
    extended = arr.tolist()
    for _ in range(horizon):
        n = len(extended)
        if method == "naive":
            val = extended[-1]
        elif method == "seasonal_naive":
            idx = n - sp
            val = extended[idx] if idx >= 0 else extended[-1]
        else:
            tail = extended[-w:] if w <= n else extended
            val = float(np.mean(tail))
        fc.append(float(val))
        extended.append(val)

    lower = [f - z * resid_std for f in fc]
    upper = [f + z * resid_std for f in fc]

    if resid.size:
        mae = float(np.mean(np.abs(resid)))
        rmse = float(np.sqrt(np.mean(resid ** 2)))
        mape = _mape(arr, method, sp, w)
    else:
        mae = rmse = mape = 0.0

    metrics = {"mae": mae, "rmse": rmse, "mape": mape, "n_train": float(arr.size)}
    return PredictionResult(
        method=method,
        horizon=horizon,
        forecast=fc,
        lower=lower,
        upper=upper,
        metrics=metrics,
        residual_std=resid_std,
    )


def evaluate_actual_vs_pred(actual, pred):
    a = np.asarray(actual, dtype=float)
    p = np.asarray(pred, dtype=float)
    resid = a - p
    mae = float(np.mean(np.abs(resid)))
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    nz = a != 0
    mape = float(np.mean(np.abs(resid[nz] / a[nz])) * 100) if nz.any() else 0.0
    return {"mae": mae, "rmse": rmse, "mape": mape}
