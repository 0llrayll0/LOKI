"""Endpoint de health check."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.database import check_db_health, check_redis_health

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check da API e do banco")
def health() -> JSONResponse:
    """200 ok se DB e Redis respondem; 503 degraded caso contrário."""
    service = get_settings().service_name
    if check_db_health() and check_redis_health():
        return JSONResponse(content={"status": "ok", "service": service})
    return JSONResponse(status_code=503, content={"status": "degraded", "service": service})
