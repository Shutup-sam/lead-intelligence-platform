from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.core.database import get_db
from app.core.redis_client import redis_client


async def get_redis() -> Redis:
    """Dependency that yields the active Redis client."""
    return redis_client


__all__ = ["get_db", "get_redis", "AsyncSession"]
