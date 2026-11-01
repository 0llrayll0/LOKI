"""Factory da aplicação LOKI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.ai import router as ai_router
from app.api.routes.ai_providers import router as ai_providers_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.demo import router as demo_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.learning import router as learning_router
from app.api.routes.models import router as models_router
from app.api.routes.pattern import router as pattern_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.providers import router as providers_router
from app.api.routes.risk import router as risk_router
from app.api.routes.scenario import router as scenario_router
from app.api.routes.stream import router as stream_router
from app.core.auth import ApiTokenMiddleware
from app.core.config import get_settings
from app.core.core import get_core
from app.core.errors import (
    BodyLimitMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers,
)
from app.core.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    core = get_core()
    core.scheduler.start()
    app.state.core = core
    logger.info(
        "api_start",
        service=settings.service_name,
        port=settings.api_port,
        environment=settings.environment,
    )
    yield
    core.scheduler.stop()
    logger.info("api_stop", service=settings.service_name)


def create_app() -> FastAPI:
    """Cria o FastAPI com título, versão, routers e handlers de erro."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.environment)
    app = FastAPI(
        title="LOKI — Predictive Intelligence System",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    # rejeição precoce de Content-Length acima de LOKI_MAX_UPLOAD_MB (413 com
    # envelope) — o uvicorn não expõe limite de corpo de requisição (sem
    # --limit-max-request-size nesta versão), então o corte é nossa responsabilidade
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(ApiTokenMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    # CORS para dev frontend; keep allow_origins explícitos (sem "*
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:4173",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(ai_router)
    app.include_router(ai_providers_router)
    app.include_router(datasets_router)
    app.include_router(demo_router)
    app.include_router(models_router)
    app.include_router(knowledge_router)
    app.include_router(providers_router)
    app.include_router(predictions_router)
    app.include_router(pattern_router)
    app.include_router(risk_router)
    app.include_router(scenario_router)
    app.include_router(learning_router)
    app.include_router(stream_router)
    return app


# Nota: não há instância `app` em nível de módulo de propósito.
# O container sobe com `uvicorn app.main:create_app --factory`; manter uma
# instância aqui criaria um segundo FastAPI (duplo boot) e executaria
# settings/logging no import. Testes usam `create_app()` diretamente.
