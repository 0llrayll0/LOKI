"""Rotas de datasets — upload, consulta e preparação (FASE 2).

Consome o pipeline `app.data` (ingest → validate → profile → prepare) e grava
os metadados em `datasets` / `dataset_versions`. O path do artefato é montado
SOMENTE com o UUID gerado para o dataset (`{datasets_dir}/{uuid}/v{n}/`) — o
nome do arquivo enviado nunca vira parte do path. Uploads passam por
whitelist de extensão e leitura em chunks com limite `LOKI_MAX_UPLOAD_MB`.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.data.errors import DataError

# `_read` é o leitor do próprio pipeline (csv/json/xlsx/parquet com sniff de
# separador e codificação); importar evita duplicar a lógica ao reabrir o
# artefato imutável para o prepare.
from app.data.ingest import _read as _read_artifact
from app.data.ingest import ingest
from app.data.prepare import prepare
from app.data.profile import profile_dataset
from app.data.validate import validate_dataframe
from app.database import get_session
from app.database.models import Dataset, DatasetVersion
from app.schemas.datasets import (
    DatasetDetail,
    DatasetSummary,
    DatasetVersionDetail,
    DatasetVersionSummary,
    PrepareRequest,
    PrepareResponse,
    UploadResponse,
)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

ALLOWED_EXTENSIONS = (".csv", ".tsv", ".txt", ".json", ".jsonl", ".ndjson", ".xlsx", ".parquet")
_CHUNK_BYTES = 1 << 20  # leitura do upload em blocos de 1 MiB

SessionDep = Annotated[Session, Depends(get_session)]


def _version_summary(row: DatasetVersion) -> DatasetVersionSummary:
    """Resumo de uma versão (sem profile/splits pesados)."""
    return DatasetVersionSummary(
        id=row.id,
        version=row.version,
        filename=row.filename,
        format=row.format,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        rows=row.rows,
        cols=row.cols,
        created_at=row.created_at,
        prepared=row.splits is not None,
    )


def _dataset_or_404(session: Session, dataset_id: str) -> Dataset:
    """Carrega o dataset por id (UUID) ou levanta o 404 do envelope de erros."""
    try:
        parsed = uuid.UUID(dataset_id)
    except ValueError as exc:
        raise NotFoundError(f"dataset '{dataset_id}' não encontrado") from exc
    dataset = session.get(Dataset, parsed)
    if dataset is None:
        raise NotFoundError(f"dataset '{dataset_id}' não encontrado")
    return dataset


def _version_or_404(session: Session, dataset: Dataset, version: int) -> DatasetVersion:
    """Carrega a versão dentro do dataset ou levanta o 404 do envelope."""
    row = session.scalar(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset.id,
            DatasetVersion.version == version,
        )
    )
    if row is None:
        raise NotFoundError(f"versão {version} do dataset '{dataset.name}' não encontrada")
    return row


def _spool_upload(upload: UploadFile, dest: Path, *, limit_mb: int) -> None:
    """Copia o upload para `dest` em chunks, abortando acima do limite.

    O destino é um temp file criado pelo SO (sufixo = extensão já validada) —
    nunca deriva do nome enviado. DataError se passar de `LOKI_MAX_UPLOAD_MB`.
    """
    limit_bytes = limit_mb * 1024 * 1024
    written = 0
    with open(dest, "wb") as out:
        while chunk := upload.file.read(_CHUNK_BYTES):
            written += len(chunk)
            if written > limit_bytes:
                raise DataError(
                    f"arquivo excede o limite de {limit_mb} MB: envio abortado "
                    f"após {written} bytes"
                )
            out.write(chunk)


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=201,
    summary="Envia um arquivo (multipart) e cria a versão do dataset",
)
def upload_dataset(
    session: SessionDep,
    file: Annotated[UploadFile, File(...)],
    name: Annotated[str, Form(...)],
    description: str | None = Form(None),
) -> UploadResponse:
    """Ingestão + validação + profile; 400 com envelope para arquivo inválido."""
    settings = get_settings()
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DataError(
            f"extensão não suportada: '{ext or filename}' — use: "
            + ", ".join(ALLOWED_EXTENSIONS)
        )
    clean_name = name.strip()
    if not clean_name or len(clean_name) > 255:
        raise DataError("name inválido: informe de 1 a 255 caracteres")

    dataset = session.scalar(select(Dataset).where(Dataset.name == clean_name))
    if dataset is None:
        dataset = Dataset(
            name=clean_name,
            description=description,
            created_at=datetime.now(UTC),
        )
        session.add(dataset)
        session.flush()  # materializa o UUID usado no path
    next_version = (
        session.scalar(
            select(func.max(DatasetVersion.version)).where(
                DatasetVersion.dataset_id == dataset.id
            )
        )
        or 0
    ) + 1

    tmp = Path(tempfile.mkstemp(prefix="loki_upload_", suffix=ext)[1])
    try:
        _spool_upload(file, tmp, limit_mb=settings.max_upload_mb)
        try:
            ingested = ingest(
                tmp,
                dataset_id=str(dataset.id),
                version=next_version,
                datasets_dir=settings.datasets_dir,
                max_upload_mb=settings.max_upload_mb,
            )
            validate_dataframe(ingested.dataframe, raw_columns=ingested.raw_columns)
            profile = profile_dataset(ingested.dataframe)
        except DataError:
            # limpa a cópia parcial gravada pela ingestão antes de propagar
            shutil.rmtree(
                Path(settings.datasets_dir) / str(dataset.id) / f"v{next_version}",
                ignore_errors=True,
            )
            raise
        row = DatasetVersion(
            dataset_id=dataset.id,
            version=next_version,
            filename=filename,
            format=ingested.format,
            sha256=ingested.sha256,
            size_bytes=ingested.size_bytes,
            rows=ingested.rows,
            cols=ingested.cols,
            profile=profile,
            transformations=[],
            splits=None,
            path=ingested.path,
            created_at=datetime.now(UTC),
        )
        session.add(row)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        tmp.unlink(missing_ok=True)

    return UploadResponse(
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        version=_version_summary(row),
    )


@router.get(
    "/",
    response_model=list[DatasetSummary],
    summary="Lista datasets com resumo da última versão",
)
def list_datasets(session: SessionDep) -> list[DatasetSummary]:
    """Lista todos os datasets (mais recentes primeiro) + última versão."""
    datasets = session.scalars(
        select(Dataset).order_by(Dataset.created_at.desc(), Dataset.name)
    ).all()
    counts = dict(
        session.execute(
            select(DatasetVersion.dataset_id, func.count(DatasetVersion.id)).group_by(
                DatasetVersion.dataset_id
            )
        ).all()
    )
    items: list[DatasetSummary] = []
    for dataset in datasets:
        last = session.scalar(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset.id)
            .order_by(DatasetVersion.version.desc())
            .limit(1)
        )
        items.append(
            DatasetSummary(
                id=dataset.id,
                name=dataset.name,
                description=dataset.description,
                created_at=dataset.created_at,
                versions_count=counts.get(dataset.id, 0),
                last_version=_version_summary(last) if last else None,
            )
        )
    return items


@router.get("/{dataset_id}", response_model=DatasetDetail, summary="Detalhe do dataset")
def dataset_detail(session: SessionDep, dataset_id: str) -> DatasetDetail:
    """Detalhe do dataset com todas as versões."""
    dataset = _dataset_or_404(session, dataset_id)
    versions = session.scalars(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version)
    ).all()
    return DatasetDetail(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at,
        versions=[_version_summary(row) for row in versions],
    )


@router.get(
    "/{dataset_id}/versions/{version}",
    response_model=DatasetVersionDetail,
    summary="Metadados, profile, transformations e splits de uma versão",
)
def dataset_version_detail(
    session: SessionDep, dataset_id: str, version: int
) -> DatasetVersionDetail:
    """Versão completa (profile + etapas + splits gravados pelo prepare)."""
    dataset = _dataset_or_404(session, dataset_id)
    row = _version_or_404(session, dataset, version)
    return DatasetVersionDetail(
        id=row.id,
        dataset_id=row.dataset_id,
        version=row.version,
        filename=row.filename,
        format=row.format,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        rows=row.rows,
        cols=row.cols,
        created_at=row.created_at,
        profile=row.profile,
        transformations=row.transformations,
        splits=row.splits,
    )


def _json_safe(value):
    import math
    # Timestamps / datetime
    if hasattr(value, "isoformat"):
        return value.isoformat()
    # pandas NaN/Inf -> None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if value is None:
        return None
    return value


@router.get(
    "/{dataset_id}/versions/{version}/sample",
    summary="Amostra das primeiras linhas da versão do dataset",
)
def dataset_version_sample(
    session: SessionDep,
    dataset_id: str,
    version: int,
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    settings = get_settings()
    dataset = _dataset_or_404(session, dataset_id)
    row = _version_or_404(session, dataset, version)

    datasets_dir = Path(settings.datasets_dir).resolve()
    artifact = Path(row.path).resolve()
    try:
        artifact.relative_to(datasets_dir)
    except ValueError as exc:
        raise DataError("caminho do artefato fora de datasets_dir") from exc
    if not artifact.is_file():
        raise NotFoundError(f"artefato da versão {version} não encontrado")

    df, _raw = _read_artifact(artifact, row.format)
    head = df.head(limit)
    columns = [str(c) for c in head.columns]
    rows = []
    for rec in head.to_dict(orient="records"):
        rows.append({str(k): _json_safe(v) for k, v in rec.items()})
    return {"columns": columns, "rows": rows}


@router.post(
    "/{dataset_id}/versions/{version}/prepare",
    response_model=PrepareResponse,
    summary="Executa o prepare (limpeza opcional + splits) da versão",
)
def prepare_dataset_version(
    session: SessionDep,
    dataset_id: str,
    version: int,
    payload: PrepareRequest,
) -> PrepareResponse:
    """Roda `app.data.prepare` e persiste splits/transformations na versão.

    400 (envelope) se o target não existir, for constante ou houver coluna
    idêntica a ele (vazamento); os splits são imutáveis — repetir o prepare
    na mesma versão também responde 400.
    """
    settings = get_settings()
    dataset = _dataset_or_404(session, dataset_id)
    row = _version_or_404(session, dataset, version)

    df, _raw_columns = _read_artifact(Path(row.path), row.format)
    target = payload.target_column
    if target is not None and target in df.columns and df[target].nunique(dropna=True) <= 1:
        raise DataError(f"target '{target}' é constante — escolha uma coluna variável")

    result = prepare(
        df,
        output_dir=Path(settings.datasets_dir) / str(dataset.id) / f"v{row.version}" / "prepared",
        target=target,
        strategy=payload.strategy,
        time_col=payload.time_col,
        ratios=payload.ratios,
        missing=payload.missing,
        outliers=payload.outliers,
    )
    row.splits = result.splits
    row.transformations = result.transformations
    session.commit()
    return PrepareResponse(
        dataset_id=dataset.id,
        version=row.version,
        splits=result.splits,
        transformations=result.transformations,
        leakage_flags=result.leakage_flags,
    )
