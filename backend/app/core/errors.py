"""Erros de domínio, handlers globais e limite de corpo da API."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Receive, Scope, Send

from app.core.config import get_settings
from app.data.errors import DataError

logger = structlog.get_logger(__name__)

# Folga do Content-Length sobre LOKI_MAX_UPLOAD_MB: cobre o overhead do
# multipart (boundary + campos de formulário). O limite do ARQUIVO continua
# sendo aplicado byte a byte no spool do upload (400 invalid_data).
_BODY_LIMIT_SLACK_BYTES = 2 * 1024 * 1024


class NotFoundError(Exception):
    """Erro de domínio: recurso não encontrado."""


class ConflictError(Exception):
    """Erro de domínio: conflito de estado (dataset/versão já existe)."""


def _error_payload(code: str, message: str) -> dict:
    return {"status": "error", "error": {"code": code, "message": message}}


class BodyLimitMiddleware:
    """Rejeita Content-Length acima do limite ANTES de ler o corpo (413 com envelope).

    Evita bufferizar uploads gigantes. Corpos sem Content-Length (chunked) caiam
    no limite byte a byte do spool (`_spool_upload`). O limite efetivo é
    `LOKI_MAX_UPLOAD_MB + _BODY_LIMIT_SLACK_BYTES`.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value for key, value in scope.get("headers", [])
        }
        raw_length = headers.get("content-length", b"")
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            length = -1
        if length >= 0:
            settings = get_settings()
            limit = settings.max_upload_mb * 1024 * 1024 + _BODY_LIMIT_SLACK_BYTES
            if length > limit:
                logger.warning(
                    "payload_too_large",
                    path=scope.get("path"),
                    content_length=length,
                    limit_bytes=limit,
                )
                response = JSONResponse(
                    status_code=413,
                    content=_error_payload(
                        "payload_too_large",
                        f"corpo da requisição excede o limite de "
                        f"{settings.max_upload_mb} MB (Content-Length: {length} bytes)",
                    ),
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def register_exception_handlers(app: FastAPI) -> None:
    """Registra os exception handlers globais do app."""

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        message = str(exc) or "Recurso não encontrado"
        logger.warning("not_found", path=request.url.path, detail=message)
        return JSONResponse(status_code=404, content=_error_payload("not_found", message))

    @app.exception_handler(ConflictError)
    async def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
        message = str(exc) or "Conflito de estado"
        logger.warning("conflict", path=request.url.path, detail=message)
        return JSONResponse(status_code=409, content=_error_payload("conflict", message))

    @app.exception_handler(DataError)
    async def handle_data_error(request: Request, exc: DataError) -> JSONResponse:
        message = str(exc) or "Falha no processamento do dado"
        logger.warning("data_error", path=request.url.path, detail=message)
        return JSONResponse(status_code=400, content=_error_payload("invalid_data", message))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """404/405 (e demais HTTPException do Starlette) no envelope de erro."""
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        code = {404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "http_error"
        )
        logger.warning(
            "http_exception",
            path=request.url.path,
            status=exc.status_code,
            detail=message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(code, message),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        # NaN/Infinity em campo numérico é DADO inválido (não erro estrutural
        # de formulário): responde 400 invalid_data em vez de 422.
        non_finite = [item for item in errors if item.get("type") == "finite_number"]
        if non_finite and len(non_finite) == len(errors):
            fields = sorted(
                {str(item["loc"][0]) for item in non_finite if item.get("loc")}
            )
            message = "valores não-finitos (NaN ou Infinity)"
            if fields:
                message += f" nos campos: {', '.join(fields)}"
            logger.warning(
                "validation_error", path=request.url.path, fields=fields, reason="non_finite"
            )
            return JSONResponse(
                status_code=400, content=_error_payload("invalid_data", message)
            )
        fields = sorted({str(item["loc"][-1]) for item in errors if item.get("loc")})
        message = "Dados de entrada inválidos"
        if fields:
            message += f" nos campos: {', '.join(fields)}"
        logger.warning("validation_error", path=request.url.path, fields=fields)
        return JSONResponse(
            status_code=422,
            content=_error_payload("validation_error", message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=_error_payload("internal_error", "Internal server error"),
        )


class RequestLoggingMiddleware:
    """Loga request_id, method, path, status e latência de cada requisição HTTP."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                status_holder["status"] = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "request",
                request_id=request_id,
                method=scope.get("method"),
                path=scope.get("path"),
                status=status_holder["status"],
                latency_ms=latency_ms,
            )
