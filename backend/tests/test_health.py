import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AI Lead Intelligence Platform"
    assert data["health_url"] == "/health"


@pytest.mark.asyncio
async def test_health_endpoint_healthy(client: AsyncClient):
    # Mock healthy DB and Redis responses
    with patch(
        "app.api.v1.health.check_database_health",
        return_value={"status": "connected", "latency_ms": 1.2, "pgvector_ready": True},
    ), patch(
        "app.api.v1.health.check_redis_health",
        return_value={"status": "connected", "latency_ms": 0.5, "ping": True},
    ):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["database"]["status"] == "connected"
        assert data["services"]["database"]["pgvector_ready"] is True
        assert data["services"]["redis"]["status"] == "connected"


@pytest.mark.asyncio
async def test_api_v1_health_endpoint(client: AsyncClient):
    with patch(
        "app.api.v1.health.check_database_health",
        return_value={"status": "connected", "latency_ms": 1.5, "pgvector_ready": True},
    ), patch(
        "app.api.v1.health.check_redis_health",
        return_value={"status": "connected", "latency_ms": 0.4, "ping": True},
    ):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_endpoint_degraded_when_db_down(client: AsyncClient):
    with patch(
        "app.api.v1.health.check_database_health",
        return_value={"status": "error", "error": "Connection refused", "pgvector_ready": False},
    ), patch(
        "app.api.v1.health.check_redis_health",
        return_value={"status": "connected", "latency_ms": 0.5, "ping": True},
    ):
        response = await client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["database"]["status"] == "error"
        assert data["services"]["redis"]["status"] == "connected"


@pytest.mark.asyncio
async def test_live_services_health(client: AsyncClient):
    """Integration test checking real PostgreSQL + pgvector and Redis connectivity."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["database"]["status"] == "connected"
    assert data["services"]["database"]["pgvector_ready"] is True
    assert data["services"]["database"]["latency_ms"] is not None
    assert data["services"]["redis"]["status"] == "connected"
    assert data["services"]["redis"]["ping"] is True

