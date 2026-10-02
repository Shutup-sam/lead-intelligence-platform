import time
from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.core.config import settings

# Async database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> Dict[str, Any]:
    """
    Checks PostgreSQL connection and verifies if the pgvector extension is installed.
    Returns status, latency in milliseconds, and pgvector readiness.
    """
    start_time = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            # Check basic query connectivity
            await session.execute(text("SELECT 1"))
            
            # Check if pgvector extension is installed
            vector_res = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            has_vector = vector_res.scalar_one_or_none() is not None
            
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status": "connected",
                "latency_ms": duration_ms,
                "pgvector_ready": has_vector,
            }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "error",
            "latency_ms": duration_ms,
            "pgvector_ready": False,
            "error": str(exc),
        }
