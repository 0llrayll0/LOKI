from __future__ import annotations

import hmac

from starlette.types import Receive, Scope, Send

from app.core.config import get_settings


class ApiTokenMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        settings = get_settings()
        token = settings.api_token
        path = scope.get("path", "")
        if not token or not path.startswith("/api"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v for k, v in scope.get("headers", [])}
        provided = ""
        auth = headers.get("authorization", b"").decode("latin-1")
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
        if not provided:
            provided = headers.get("x-api-key", b"").decode("latin-1")
        if not hmac.compare_digest(provided, token):
            from fastapi.responses import JSONResponse

            resp = JSONResponse(status_code=401, content={"status": "error", "error": {"code": "unauthorized", "message": "token inválido ou ausente"}})
            await resp(scope, receive, send)
            return
        await self.app(scope, receive, send)
