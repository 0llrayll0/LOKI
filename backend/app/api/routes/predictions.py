"""Rotas de previsão baseline (Fase 6)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.data.ingest import _read as _read_artifact
from app.database import get_session
from app.database.models import Dataset, DatasetVersion
from app.prediction import predict

router = APIRouter(prefix="/api/predictions", tags=["predictions"])
SessionDep = Annotated[Session, Depends(get_session)]


class PredictionOut(BaseModel):
    dataset_id: str
    version: int
    target_col: str
    method: str
    horizon: int
    forecast: list[float]
    lower: list[float]
    upper: list[float]
    metrics: dict[str, float]
    residual_std: float


def _load_series(session: Session, dataset_id: str, version: int | None, target_col: str):
    try:
        parsed = uuid.UUID(dataset_id)
    except ValueError as exc:
        raise NotFoundError(f"dataset '{dataset_id}' não encontrado") from exc
    dataset = session.get(Dataset, parsed)
    if dataset is None:
        raise NotFoundError(f"dataset '{dataset_id}' não encontrado")
    if version is None:
        row = session.scalar(
            __import__("sqlalchemy", fromlist=["select"]).select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset.id)
            .order_by(DatasetVersion.version.desc())
            .limit(1)
        )
    else:
        row = session.scalar(
            __import__("sqlalchemy", fromlist=["select"]).select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset.id, DatasetVersion.version == version)
            .limit(1)
        )
    if row is None:
        raise NotFoundError("versão não encontrada")
    df, _ = _read_artifact(Path(row.path), row.format)
    if target_col not in df.columns:
        raise NotFoundError(f"coluna '{target_col}' não encontrada")
    return df[target_col].tolist(), row.version


@router.get("/", response_model=PredictionOut)
def run_prediction(
    session: SessionDep,
    dataset_id: str = Query(...),
    target_col: str = Query(...),
    horizon: int = Query(7, ge=1, le=60),
    method: str = Query("naive"),
    version: int | None = Query(None),
    seasonal_period: int | None = Query(None),
    window: int | None = Query(None),
) -> PredictionOut:
    values, v = _load_series(session, dataset_id, version, target_col)
    res = predict(
        values,
        horizon=horizon,
        method=method,
        seasonal_period=seasonal_period,
        window=window,
    )  # type: ignore[arg-type]
    return PredictionOut(
        dataset_id=dataset_id,
        version=v,
        target_col=target_col,
        method=res.method,
        horizon=res.horizon,
        forecast=res.forecast,
        lower=res.lower,
        upper=res.upper,
        metrics=res.metrics,
        residual_std=res.residual_std,
    )
