"""Testes das Settings (prefixo LOKI_*, .env e resolução da URL do banco)."""

from app.core.config import Settings, get_settings

_LOKI_VARS = (
    "LOKI_API_PORT",
    "LOKI_SERVICE_NAME",
    "LOKI_LOG_LEVEL",
    "LOKI_ENVIRONMENT",
    "LOKI_DATABASE_URL",
)

_POSTGRES_VARS = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
)


def test_defaults(monkeypatch):
    for key in (*_LOKI_VARS, *_POSTGRES_VARS):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.api_port == 8100
    assert settings.service_name == "loki-api"
    assert settings.log_level == "INFO"
    assert settings.environment == "dev"


def test_prefixo_loki(monkeypatch):
    monkeypatch.setenv("LOKI_API_PORT", "9999")
    settings = Settings(_env_file=None)
    assert settings.api_port == 9999


def test_ignora_variavel_sem_prefixo(monkeypatch):
    monkeypatch.setenv("API_PORT", "1234")
    settings = Settings(_env_file=None)
    assert settings.api_port == 8100


def test_ler_arquivo_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LOKI_API_PORT=8200\n")
    settings = Settings(_env_file=env_file)
    assert settings.api_port == 8200


def test_resolve_database_url_direta():
    url = "postgresql+psycopg://user:pass@dbhost:5432/lokidb"
    settings = Settings(_env_file=None, database_url=url)
    assert settings.resolve_database_url() == url


def test_resolve_database_url_montada_de_postgres_env(monkeypatch):
    for key in _POSTGRES_VARS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LOKI_DATABASE_URL", "")
    monkeypatch.setenv("POSTGRES_USER", "loki")
    monkeypatch.setenv("POSTGRES_PASSWORD", "senha_dev")
    monkeypatch.setenv("POSTGRES_HOST", "db-alias")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "loki_db")
    settings = Settings(_env_file=None, database_url="")
    assert settings.resolve_database_url() == "postgresql+psycopg://loki:senha_dev@db-alias:5433/loki_db"


def test_get_settings_cacheado():
    assert get_settings() is get_settings()
    assert isinstance(get_settings(), Settings)
