import asyncio
import logging
import time
from typing import Optional
from app.core.redis_client import redis_client

logger = logging.getLogger("lead_intelligence.crawler.rate_limiter")


class DomainRateLimiter:
    """
    Coordinates distributed crawling across worker processes using Redis:
    1. Distributed domain locks: prevents multiple workers from crawling the same domain concurrently.
    2. Timestamp-based politeness delay: ensures consecutive requests to the same domain maintain polite intervals.
    """

    def __init__(self, client=None):
        self.client = client or redis_client

    async def acquire_lock(self, domain: str, timeout_seconds: int = 180) -> bool:
        """
        Attempts to acquire an exclusive distributed lock for a domain using Redis SET NX.
        Returns True if acquired, False if the domain is currently locked by another worker.
        """
        if not domain:
            return True
        key = f"crawler:lock:{domain.lower()}"
        acquired = await self.client.set(key, "locked", nx=True, ex=timeout_seconds)
        if acquired:
            logger.info("Acquired domain lock for '%s' (ttl=%ds)", domain, timeout_seconds)
            return True
        logger.warning("Domain '%s' is locked by another active crawl task", domain)
        return False

    async def release_lock(self, domain: str) -> None:
        """Releases the distributed domain lock."""
        if not domain:
            return
        key = f"crawler:lock:{domain.lower()}"
        await self.client.delete(key)
        logger.info("Released domain lock for '%s'", domain)

    async def wait_polite_delay(self, domain: str, min_delay_seconds: float = 1.0) -> None:
        """
        Ensures polite inter-request delay per domain across all workers.
        Reads last request timestamp from Redis, sleeps if required, and records new timestamp.
        """
        if not domain or min_delay_seconds <= 0:
            return

        key = f"crawler:last_request:{domain.lower()}"
        now = time.time()
        last_str = await self.client.get(key)

        if last_str:
            try:
                last_time = float(last_str)
                elapsed = now - last_time
                if elapsed < min_delay_seconds:
                    wait_time = min_delay_seconds - elapsed
                    logger.debug("Rate-limiting '%s': sleeping %.2fs for politeness", domain, wait_time)
                    await asyncio.sleep(wait_time)
            except ValueError:
                pass

        # Update last request timestamp with 120s TTL
        await self.client.set(key, str(time.time()), ex=120)
