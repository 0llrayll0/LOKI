"""Testes de integração das rotas /api/datasets (FASE 2).

TestClient + SQLite em memória (override da sessão) + LOKI_DATASETS_DIR em
tmp_path — sem Postgres e sem tocar no diretório real de datasets. Os dados
usados aqui são sintéticos (CSV gerado no teste).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import datasets as datasets_route
from app.core.config import Settings, get_settings
from app.database import Base, get_session
from app.main import create_app

# Toda variável que poderia vazar do .env/shell para as Settings nos testes.
_AMBIENT_KEYS = (
    "LOKI_SERVICE_NAME",
    "LOKI_API_PORT",
    "LOKI_LOG_LEVEL",
    "LOKI_ENVIRONMENT",
    "LOKI_DATABASE_URL",
    "LOKI_DATASETS_DIR",
    "LOKI_MAX_UPLOAD_MB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "REDIS_URL",
)


def _csv(rows: int = 12) -> bytes:
    """CSV sintético: data (datetime), valor (numérico variável), categoria."""
    linhas = ["data,valor,categoria"]
    for i in range(rows):
        linhas.append(f"2024-01-{i + 1:02d},{i * 10},{'a' if i % 2 else 'b'}")
    return "\n".join(linhas).encode()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client com app real, SQLite em memória e datasets_dir apontando p/ tmp."""
    get_settings.cache_clear()
    for key in _AMBIENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    datasets_dir = tmp_path / "datasets"
    settings = Settings(_env_file=None, datasets_dir=str(datasets_dir), max_upload_mb=1)
    monkeypatch.setattr(datasets_route, "get_settings", lambda: settings)

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


def _upload(
    client,
    *,
    name: str = "vendas",
    filename: str = "dados.csv",
    content: bytes | None = None,
    description: str | None = None,
):
    data = {"name": name}
    if description is not None:
        data["description"] = description
    return client.post(
        "/api/datasets/upload",
        files={"file": (filename, content if content is not None else _csv(), "text/csv")},
        data=data,
    )


# ---------------------------------------------------------------- upload


def test_upload_ok_cria_dataset_e_versao(client):
    response = _upload(client, name="vendas", description="histórico 2024")
    assert response.status_code == 201
    body = response.json()
    assert body["dataset_name"] == "vendas"
    version = body["version"]
    assert version["version"] == 1
    assert version["format"] == "csv"
    assert version["filename"] == "dados.csv"
    assert version["rows"] == 12
    assert version["cols"] == 3
    assert version["prepared"] is False
    assert len(version["sha256"]) == 64


def test_upload_grava_original_no_datasets_dir(client, tmp_path):
    response = _upload(client, name="vendas")
    assert response.status_code == 201
    dataset_id = response.json()["dataset_id"]
    # o fixture usa tmp_path como LOKI_DATASETS_DIR: o artefato deve aparecer
    # no "host" de teste, no path montado só com o UUID (nunca com o filename)
    matches = list(tmp_path.glob("datasets/*/v1/original.csv"))
    assert len(matches) == 1
    assert matches[0].parent.parent.name == dataset_id


def test_upload_segundo_arquivo_vira_versao_2(client):
    first = _upload(client, name="vendas")
    second = _upload(client, name="vendas", filename="dados_v2.csv")
    assert first.status_code == second.status_code == 201
    assert first.json()["dataset_id"] == second.json()["dataset_id"]
    assert second.json()["version"]["version"] == 2
    detail = client.get(f"/api/datasets/{first.json()['dataset_id']}").json()
    assert [v["version"] for v in detail["versions"]] == [1, 2]


def test_upload_extensao_invalida_400_envelope(client):
    response = _upload(client, filename="virus.exe", content=b"MZ\x90\x00")
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "invalid_data"
    assert "extensão" in body["error"]["message"]
    assert client.get("/api/datasets").json() == []  # nada persistido


def test_upload_acima_do_limite_400_envelope(client):
    big = b"x" * (2 * 1024 * 1024)  # 2 MB com LOKI_MAX_UPLOAD_MB=1
    response = _upload(client, content=big)
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert "limite" in body["error"]["message"]
    assert client.get("/api/datasets").json() == []


def test_upload_corrompido_400(client):
    response = _upload(client, content=b"\x00\x01\x02\x03binario corrompido")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_data"
    assert client.get("/api/datasets").json() == []


# ------------------------------------------------------------- listagem


def test_listagem_com_resumo_da_ultima_versao(client):
    _upload(client, name="abc")
    _upload(client, name="def", filename="outro.csv")
    _upload(client, name="abc", filename="abc_v2.csv")
    response = client.get("/api/datasets")
    assert response.status_code == 200
    items = response.json()
    # mais recente primeiro: "def" foi enviado depois de "abc"
    assert [item["name"] for item in items] == ["def", "abc"]
    abc = next(item for item in items if item["name"] == "abc")
    assert abc["versions_count"] == 2
    assert abc["last_version"]["version"] == 2
    assert abc["last_version"]["rows"] == 12
    def_item = next(item for item in items if item["name"] == "def")
    assert def_item["versions_count"] == 1


def test_listagem_vazia(client):
    assert client.get("/api/datasets").json() == []


# --------------------------------------------------------------- detalhe


def test_detalhe_do_dataset(client):
    created = _upload(client, name="vendas", description="histórico").json()
    response = client.get(f"/api/datasets/{created['dataset_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "vendas"
    assert body["description"] == "histórico"
    assert len(body["versions"]) == 1
    assert body["versions"][0]["version"] == 1


def test_detalhe_404_envelope(client):
    response = client.get(f"/api/datasets/{uuid.uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "not_found"


def test_detalhe_404_id_nao_uuid(client):
    response = client.get("/api/datasets/nao-e-uuid")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_version_detail_com_profile(client):
    created = _upload(client).json()
    dataset_id = created["dataset_id"]
    response = client.get(f"/api/datasets/{dataset_id}/versions/1")
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["rows"] == 12
    assert [col["name"] for col in body["profile"]["columns"]] == ["data", "valor", "categoria"]
    assert body["transformations"] == []
    assert body["splits"] is None


def test_version_404_envelope(client):
    created = _upload(client).json()
    response = client.get(f"/api/datasets/{created['dataset_id']}/versions/99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --------------------------------------------------------------- prepare


def test_prepare_random(client, tmp_path):
    created = _upload(client).json()
    dataset_id = created["dataset_id"]
    response = client.post(
        f"/api/datasets/{dataset_id}/versions/1/prepare",
        json={"target_column": "valor", "strategy": "random"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["splits"]["strategy"] == "random"
    assert body["splits"]["target"] == "valor"
    assert body["splits"]["splits"] == {
        "train": {"file": "train.parquet", "rows": 8},
        "val": {"file": "val.parquet", "rows": 1},
        "test": {"file": "test.parquet", "rows": 3},
    }
    assert {step["step"] for step in body["transformations"]} >= {"missing", "outliers", "split"}
    # splits gravados no disco do "host" de teste + registrados na versão
    assert len(list(tmp_path.glob("datasets/*/v1/prepared/*.parquet"))) == 3
    detail = client.get(f"/api/datasets/{dataset_id}/versions/1").json()
    assert detail["splits"]["total_rows"] == 12
    assert detail["transformations"]


def test_prepare_temporal(client):
    created = _upload(client).json()
    response = client.post(
        f"/api/datasets/{created['dataset_id']}/versions/1/prepare",
        json={"strategy": "temporal", "time_col": "data"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["splits"]["strategy"] == "temporal"
    assert body["splits"]["time_col"] == "data"
    assert body["splits"]["splits"]["train"]["rows"] == 8


def test_prepare_target_inexistente_400(client):
    created = _upload(client).json()
    response = client.post(
        f"/api/datasets/{created['dataset_id']}/versions/1/prepare",
        json={"target_column": "nao_existe"},
    )
    assert response.status_code == 400
    assert "não existe" in response.json()["error"]["message"]


def test_prepare_target_constante_400(client):
    csv = "data,y\n2024-01-01,1\n2024-01-02,1\n2024-01-03,1\n2024-01-04,1\n"
    created = _upload(client, name="constante", content=csv.encode()).json()
    response = client.post(
        f"/api/datasets/{created['dataset_id']}/versions/1/prepare",
        json={"target_column": "y"},
    )
    assert response.status_code == 400
    assert "constante" in response.json()["error"]["message"]


def test_prepare_target_identico_400(client):
    csv = "a,b\n1,1\n2,2\n3,3\n4,4\n"
    created = _upload(client, name="vazamento", content=csv.encode()).json()
    response = client.post(
        f"/api/datasets/{created['dataset_id']}/versions/1/prepare",
        json={"target_column": "a"},
    )
    assert response.status_code == 400
    assert "vazamento" in response.json()["error"]["message"]


def test_prepare_repetido_400_imutavel(client):
    created = _upload(client).json()
    url = f"/api/datasets/{created['dataset_id']}/versions/1/prepare"
    assert client.post(url, json={"target_column": "valor"}).status_code == 200
    response = client.post(url, json={"target_column": "valor"})
    assert response.status_code == 400
    assert "imutável" in response.json()["error"]["message"]


def test_prepare_422_envelope(client):
    created = _upload(client).json()
    response = client.post(
        f"/api/datasets/{created['dataset_id']}/versions/1/prepare",
        json={"strategy": "banana"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "validation_error"


def test_prepare_404_envelope(client):
    created = _upload(client).json()
    response = client.post(
        f"/api/datasets/{created['dataset_id']}/versions/7/prepare", json={}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
