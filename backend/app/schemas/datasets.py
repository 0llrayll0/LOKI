"""Schemas Pydantic das rotas de datasets (FASE 2).

`profile`, `splits` e `transformations` são dict/list genéricos porque já
vêm validados da origem (pipeline `app.data` + colunas JSON do banco).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# `allow_inf_nan=False` POR ITEM: aplicado à tupla inteira, o pydantic tenta
# validar os floats na própria tupla e levanta TypeError (500). No item, NaN e
# Infinity viram erro de validação — o handler converte para 400 invalid_data.
_FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class DatasetVersionSummary(BaseModel):
    """Resumo de uma versão de ingestão (usado em listagem e detalhe)."""

    id: uuid.UUID
    version: int
    filename: str
    format: str
    sha256: str
    size_bytes: int
    rows: int
    cols: int
    created_at: datetime
    prepared: bool = False


class DatasetSummary(BaseModel):
    """Item da listagem de datasets, com o resumo da última versão."""

    id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    versions_count: int
    last_version: DatasetVersionSummary | None = None


class DatasetDetail(BaseModel):
    """Detalhe de um dataset e todas as suas versões."""

    id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    versions: list[DatasetVersionSummary]


class DatasetVersionDetail(BaseModel):
    """Metadados + perfil + etapas + splits de uma versão."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    version: int
    filename: str
    format: str
    sha256: str
    size_bytes: int
    rows: int
    cols: int
    created_at: datetime
    profile: dict
    transformations: list[dict]
    splits: dict | None = None


class UploadResponse(BaseModel):
    """201 do POST /upload: dataset criado/atualizado + versão gerada."""

    dataset_id: uuid.UUID
    dataset_name: str
    version: DatasetVersionSummary


class PrepareRequest(BaseModel):
    """Parâmetros do POST .../versions/{version}/prepare (defaults = pipeline)."""

    target_column: str | None = None
    strategy: Literal["random", "temporal"] = "random"
    time_col: str | None = None
    ratios: tuple[_FiniteFloat, _FiniteFloat, _FiniteFloat] = (0.7, 0.15, 0.15)
    missing: Literal["drop", "mean", "median", "ffill", "none"] = "none"
    outliers: Literal["keep", "clip"] = "keep"


class PrepareResponse(BaseModel):
    """Resumo dos splits gravados pelo prepare + flags de vazamento."""

    dataset_id: uuid.UUID
    version: int
    splits: dict
    transformations: list[dict]
    leakage_flags: list[str]
