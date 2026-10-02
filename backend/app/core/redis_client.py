import time
from typing import Dict, Any
from redis.asyncio import Redis, from_url

from app.core.config import settings

redis_client: Redis = from_url(settings.REDIS_URL, decode_responses=True)


async def check_redis_health() -> Dict[str, Any]:
    """
    Checks Redis connectivity by sending a PING command.
    Returns status, latency in milliseconds, and error details if any.
    """
    start_time = time.perf_counter()
    try:
        pong = await redis_client.ping()
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "connected" if pong else "unresponsive",
            "latency_ms": duration_ms,
            "ping": bool(pong),
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "error",
            "latency_ms": duration_ms,
            "ping": False,
            "error": str(exc),
        }


async def close_redis() -> None:
    """Close redis connection pool on shutdown."""
    await redis_client.close()
