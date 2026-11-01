"""Testes do endpoint /health e dos handlers de erro (TestClient, sem subir servidor)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

import app.main as main_module
from app.api.routes import health as health_route
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.main import create_app

# Toda variável que poderia vazar do .env/shell para as Settings usadas nos testes.
_AMBIENT_KEYS = (
    "LOKI_SERVICE_NAME",
    "LOKI_API_PORT",
    "LOKI_LOG_LEVEL",
    "LOKI_ENVIRONMENT",
    "LOKI_DATABASE_URL",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "REDIS_URL",
)


@pytest.fixture(autouse=True)
def settings_isoladas_do_ambiente(monkeypatch):
    """Zera o cache e força Settings sem .env, ignorando shell/.env do host."""
    get_settings.cache_clear()
    for key in _AMBIENT_KEYS:
        monkeypatch.delenv(key, raising=False)

    def _settings_sem_env() -> Settings:
        return Settings(_env_file=None)

    monkeypatch.setattr(main_module, "get_settings", _settings_sem_env)
    monkeypatch.setattr(health_route, "get_settings", _settings_sem_env)
    yield
    get_settings.cache_clear()


def test_health_ok(monkeypatch):
    monkeypatch.setattr(health_route, "check_db_health", lambda: True)
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "loki-api"}


def test_health_degraded_sem_banco(monkeypatch):
    monkeypatch.setattr(health_route, "check_db_health", lambda: False)
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "service": "loki-api"}


def test_metadados_da_app():
    schema = create_app().openapi()
    assert schema["info"]["title"] == "LOKI — Predictive Intelligence System"
    assert schema["info"]["version"] == "0.1.0"


def test_not_found_error_vira_404_estruturado():
    app = create_app()

    @app.get("/recurso-ausente")
    def recurso_ausente():
        raise NotFoundError("recurso 42 não encontrado")

    with TestClient(app) as client:
        response = client.get("/recurso-ausente")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "not_found"
    assert "recurso 42" in body["error"]["message"]


def test_erro_inesperado_vira_500_estruturado_sem_vazar_detalhes():
    app = create_app()

    @app.get("/quebra")
    def quebra():
        raise RuntimeError("detalhe interno sensível")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/quebra")
    assert response.status_code == 500
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "internal_error"
    assert "sensível" not in response.text


def test_validation_error_vira_422_estruturado():
    class Payload(BaseModel):
        nome: str
        idade: int

    app = create_app()

    @app.post("/valida")
    def valida(payload: Payload) -> dict:
        return {"nome": payload.nome}

    with TestClient(app) as client:
        response = client.post("/valida", json={"nome": 123})
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "validation_error"
    assert "Dados de entrada inválidos" in body["error"]["message"]
