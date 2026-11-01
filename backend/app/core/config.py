"""Configuração da API LOKI — pydantic-settings com prefixo LOKI_*."""

import os
from functools import lru_cache
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variáveis de ambiente LOKI_* (lê o arquivo .env se existir)."""

    model_config = SettingsConfigDict(
        env_prefix="LOKI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "loki-api"
    api_port: int = 8100
    log_level: str = "INFO"
    environment: str = "dev"
    database_url: str = ""
    datasets_dir: str = "./datasets"
    max_upload_mb: int = 100
    api_token: str = ""
    secret_key: str = ""

    def resolve_database_url(self) -> str:
        """URL do banco: LOKI_DATABASE_URL, ou montada a partir de POSTGRES_* (docker compose)."""
        if self.database_url:
            return self.database_url
        user = quote(os.getenv("POSTGRES_USER", "loki"), safe="")
        password = quote(os.getenv("POSTGRES_PASSWORD", ""), safe="")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "loki")
        credentials = f"{user}:{password}@" if password else f"{user}@"
        return f"postgresql+psycopg://{credentials}{host}:{port}/{database}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Instância única de Settings (cache)."""
    return Settings()
