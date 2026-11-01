"""Camada de dados: engine SQLAlchemy 2.0 (sync, psycopg3), Base e sessões."""

import os
from collections.abc import Iterator

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """Base declarativa — os modelos do app herdam dela."""


engine: Engine = create_engine(
    get_settings().resolve_database_url(),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Iterator[Session]:
    """Fornece uma sessão por requisição e fecha ao final."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_db_health() -> bool:
    """True se o banco responde a SELECT 1; False caso contrário (sem exceção)."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("db_healthcheck_failed", error_type=type(exc).__name__, error=str(exc))
        return False
    return True


def check_redis_health() -> bool:
    """True se o Redis responde a PING (ou se não estiver configurado); False caso contrário."""
    url = os.getenv("REDIS_URL")
    if not url:
        return True
    try:
        import redis  # type: ignore
    except Exception:
        return False
    try:
        client = redis.from_url(url)
        return bool(client.ping())
    except Exception as exc:
        logger.warning("redis_healthcheck_failed", error_type=type(exc).__name__, error=str(exc))
        return False
