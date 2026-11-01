from __future__ import annotations

import csv
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data.ingest import ingest
from app.data.profile import profile_dataset
from app.data.validate import validate_dataframe
from app.database import get_session
from app.database.models import Dataset, DatasetVersion, KnowledgeFact
from app.providers.url_scraper import UrlScraperProvider

router = APIRouter(prefix="/api/demo", tags=["demo"])
SessionDep = None


class ScrapeBody(BaseModel):
    url: str


@router.post("/scrape")
def scrape(body: ScrapeBody):
    provider = UrlScraperProvider(name="demo", url=body.url)
    try:
        obs = provider.fetch()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    data = obs[0].payload
    paragraphs = data.get("paragraphs", [])
    dataset = UrlScraperProvider.top_words(paragraphs)
    return {
        "title": data.get("title", ""),
        "paragraphs": paragraphs,
        "links": data.get("links", []),
        "dataset": dataset,
    }


@router.post("/seed")
def seed(session: Session = Depends(get_session)):
    """Cria um dataset demo + fatos de conhecimento para demonstração."""
    settings = get_settings()
    rows = []
    base_value = 42.0
    for i in range(1, 121):
        value = base_value + i * 1.3 + (i % 5) * 2.0 + (i % 7) * 1.5
        categoria = "a" if i % 2 else "b"
        dia = f"2024-01-{(i % 28) + 1:02d}"
        row = {"data": dia, "vendas": round(value, 2), "categoria": categoria}
        rows.append(row)

    tmp = Path(tempfile.mkstemp(prefix="loki_demo_", suffix=".csv")[1])
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["data", "vendas", "categoria"])
        writer.writeheader()
        writer.writerows(rows)

    name = "demo-loki"
    dataset = session.scalar(select(Dataset).where(Dataset.name == name))
    if dataset is None:
        dataset = Dataset(
            name=name,
            description="Dataset de demonstração LOKI",
            created_at=datetime.now(UTC),
        )
        session.add(dataset)
        session.flush()

    q = select(func.max(DatasetVersion.version)).where(DatasetVersion.dataset_id == dataset.id)
    mx = session.scalar(q) or 0
    next_version = mx + 1

    try:
        ingested = ingest(
            tmp,
            dataset_id=str(dataset.id),
            version=next_version,
            datasets_dir=settings.datasets_dir,
        )
        validate_dataframe(ingested.dataframe, raw_columns=ingested.raw_columns)
        profile = profile_dataset(ingested.dataframe)
    except Exception as exc:
        session.rollback()
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))

    row = DatasetVersion(
        dataset_id=dataset.id,
        version=next_version,
        filename="demo.csv",
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

    # fatos demo
    facts = [
        ("demo_fonte", "Dataset demonstrativo gerado pelo /api/demo/seed"),
        ("demo_objetivo", "Validar previsões, padrões, cenários e risco"),
    ]
    for key, value in facts:
        existing = session.scalar(select(KnowledgeFact).where(KnowledgeFact.key == key))
        if existing is None:
            session.add(KnowledgeFact(
                key=key,
                value=value,
                tags=["demo"],
                source="demo",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ))

    session.commit()
    tmp.unlink(missing_ok=True)

    return {
        "status": "ok",
        "dataset_id": str(dataset.id),
        "dataset_name": dataset.name,
        "version": next_version,
        "rows": len(rows),
    }
