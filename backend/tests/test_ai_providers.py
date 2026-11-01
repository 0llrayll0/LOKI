"""Provider Hub — testes básicos (create/list/test/delete, criptografia)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import ai_providers as ai_route
from app.core.config import Settings, get_settings
from app.core.secrets import get_settings as secrets_settings
from app.database import Base, get_session
from app.main import create_app

_AMBIENT_KEYS = (
    "LOKI_SERVICE_NAME",
    "LOKI_API_PORT",
    "LOKI_LOG_LEVEL",
    "LOKI_ENVIRONMENT",
    "LOKI_DATABASE_URL",
    "LOKI_SECRET_KEY",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "REDIS_URL",
)


@pytest.fixture
def client(monkeypatch):
    get_settings.cache_clear()
    for key in _AMBIENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None, secret_key="test-secret-32chars-minimum-len!")
    monkeypatch.setattr(ai_route, "get_settings", lambda: settings, raising=False)
    monkeypatch.setattr("app.core.secrets.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models=__import__("app.database.models", fromlist=["AiProvider", "AiProviderUsage"])
    Base.metadata.create_all(engine, tables=[models.AiProvider.__table__, models.AiProviderUsage.__table__])
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


def test_create_and_list_masks_key(client):
    r = client.post("/api/ai/providers/", json={
        "name": "ollama local",
        "type": "ollama",
        "base_url": "http://127.0.0.1:9/v1",
        "api_key": "sk-secret-123456",
        "enabled": True,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_key"] is True
    assert "sk-secret" not in body["api_key_masked"]
    assert body["name"] == "ollama local"

    lst = client.get("/api/ai/providers/").json()
    assert len(lst) == 1
    assert lst[0]["id"] == body["id"]


def test_update_and_delete(client):
    r = client.post("/api/ai/providers/", json={
        "name": "p", "type": "custom", "base_url": "http://x/v1", "api_key": "key"
    })
    pid = r.json()["id"]
    upd = client.patch(f"/api/ai/providers/{pid}", json={"name": "renamed", "enabled": False})
    assert upd.status_code == 200
    assert upd.json()["name"] == "renamed"
    assert upd.json()["enabled"] is False

    d = client.delete(f"/api/ai/providers/{pid}")
    assert d.status_code == 204
    assert client.get(f"/api/ai/providers/{pid}").status_code == 404


def test_test_connection_failure_returns_false(client):
    r = client.post("/api/ai/providers/", json={
        "name": "bad", "type": "ollama", "base_url": "http://127.0.0.1:9/v1"
    })
    pid = r.json()["id"]
    t = client.post(f"/api/ai/providers/{pid}/test")
    assert t.status_code == 200
    body = t.json()
    assert body["ok"] is False
