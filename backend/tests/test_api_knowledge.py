"""Testes de integração das rotas /api/knowledge (Fase 4)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_session
from app.main import create_app


@pytest.fixture
def client(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("LOKI_DATABASE_URL", raising=False)
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_create_fact_ok(client):
    response = client.post(
        "/api/knowledge/",
        json={"key": "k1", "value": {"a": 1}, "tags": ["t"], "source": "manual"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "k1"
    assert body["value"] == {"a": 1}
    assert body["tags"] == ["t"]
    assert body["source"] == "manual"
    uuid.UUID(body["id"])


def test_create_fact_duplicado(client):
    client.post("/api/knowledge/", json={"key": "k1", "value": 1})
    r2 = client.post("/api/knowledge/", json={"key": "k1", "value": 2})
    assert r2.status_code == 400


def test_list_empty(client):
    assert client.get("/api/knowledge/").json()["items"] == []


def test_list_after_create(client):
    client.post("/api/knowledge/", json={"key": "k1", "value": 1})
    body = client.get("/api/knowledge/").json()
    assert body["total"] == 1
    assert body["items"][0]["key"] == "k1"


def test_list_filter_tag(client):
    client.post("/api/knowledge/", json={"key": "a", "value": 1, "tags": ["x"]})
    client.post("/api/knowledge/", json={"key": "b", "value": 2, "tags": ["y"]})
    body = client.get("/api/knowledge/?tag=x").json()
    assert body["total"] == 1
    assert body["items"][0]["key"] == "a"


def test_get_by_id(client):
    created = client.post("/api/knowledge/", json={"key": "k1", "value": 5}).json()
    fid = created["id"]
    r = client.get(f"/api/knowledge/{fid}")
    assert r.status_code == 200
    assert r.json()["key"] == "k1"


def test_get_by_id_404(client):
    r = client.get(f"/api/knowledge/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_get_by_id_invalid_404(client):
    r = client.get("/api/knowledge/nao-uuid")
    assert r.status_code == 404


def test_search(client):
    client.post("/api/knowledge/", json={"key": "vendas_total", "value": 10})
    client.post("/api/knowledge/", json={"key": "estoque", "value": 2})
    body = client.get("/api/knowledge/search?q=vendas").json()
    assert body["total"] == 1
    assert body["items"][0]["key"] == "vendas_total"


def test_search_empty(client):
    body = client.get("/api/knowledge/search?q=zzz").json()
    assert body["total"] == 0
    assert body["items"] == []


def test_delete_ok(client):
    created = client.post("/api/knowledge/", json={"key": "del", "value": 1}).json()
    fid = created["id"]
    r = client.delete(f"/api/knowledge/{fid}")
    assert r.status_code == 204
    r2 = client.get(f"/api/knowledge/{fid}")
    assert r2.status_code == 404


def test_delete_404(client):
    r = client.delete(f"/api/knowledge/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_invalid_404(client):
    r = client.delete("/api/knowledge/nao-uuid")
    assert r.status_code == 404
