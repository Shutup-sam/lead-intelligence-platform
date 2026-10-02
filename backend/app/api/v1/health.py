from datetime import datetime, timezone
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.core.config import settings
from app.core.database import check_database_health
from app.core.redis_client import check_redis_health

router = APIRouter(tags=["Health"])


class ServiceHealth(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    pgvector_ready: Optional[bool] = None
    ping: Optional[bool] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    environment: str
    timestamp: str
    services: Dict[str, ServiceHealth]


@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response):
    """
    Comprehensive system health check.
    Validates PostgreSQL connectivity, pgvector extension availability, and Redis connectivity.
    """
    db_health = await check_database_health()
    redis_health = await check_redis_health()

    is_db_ok = db_health.get("status") == "connected"
    is_redis_ok = redis_health.get("status") == "connected"

    overall_status = "healthy"
    if not is_db_ok or not is_redis_ok:
        overall_status = "degraded" if (is_db_ok or is_redis_ok) else "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services={
            "database": ServiceHealth(**db_health),
            "redis": ServiceHealth(**redis_health),
        },
    )
