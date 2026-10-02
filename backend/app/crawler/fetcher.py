import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from scrapling import AsyncFetcher, DynamicFetcher
from app.core.config import settings

logger = logging.getLogger("lead_intelligence.crawler.fetcher")


@dataclass
class FetchResult:
    """Holds the raw result of an HTTP or dynamic page fetch."""
    url: str
    final_url: str
    status_code: int
    content: str
    response_time_ms: float
    is_dynamic: bool = False
    error: Optional[str] = None
    headers: Dict[str, str] = None


class ScraplingFetcher:
    """
    Robust fetcher abstraction built on Scrapling.
    Implements politeness delays, per-domain concurrency locks (max 1),
    exponential backoff with jitter on transient failures, and
    controlled fallback for dynamic client-rendered pages.
    """

    def __init__(
        self,
        timeout: int = settings.CRAWLER_REQUEST_TIMEOUT,
        delay_seconds: float = settings.CRAWLER_DELAY_SECONDS,
        max_retries: int = settings.CRAWLER_MAX_RETRIES,
        user_agent: str = settings.CRAWLER_USER_AGENT,
        enable_dynamic_fallback: bool = False,
    ):
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.enable_dynamic_fallback = enable_dynamic_fallback

        # Concurrency locks and timestamp trackers per domain
        self._domain_locks: Dict[str, asyncio.Lock] = {}
        self._last_fetch_time: Dict[str, float] = {}

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def _get_domain_lock(self, domain: str) -> asyncio.Lock:
        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()
        return self._domain_locks[domain]

    async def _enforce_politeness_delay(self, domain: str) -> None:
        """Enforces configured delay between successive requests to the same domain."""
        last_time = self._last_fetch_time.get(domain)
        if last_time is not None:
            elapsed = time.time() - last_time
            if elapsed < self.delay_seconds:
                sleep_needed = self.delay_seconds - elapsed
                logger.debug("Politeness delay of %.2fs applied for domain %s", sleep_needed, domain)
                await asyncio.sleep(sleep_needed)

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetches the target URL with politeness control, retry backoff, and dynamic detection.
        """
        domain = self._get_domain(url)
        lock = self._get_domain_lock(domain)

        async with lock:
            await self._enforce_politeness_delay(domain)
            result = await self._fetch_with_retries(url)
            self._last_fetch_time[domain] = time.time()
            return result

    async def _fetch_with_retries(self, url: str) -> FetchResult:
        """Executes HTTP fetch with exponential backoff on transient errors."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        last_error: Optional[str] = None
        start_time = time.perf_counter()

        for attempt in range(self.max_retries + 1):
            fetch_start = time.perf_counter()
            try:
                # 1. Primary: Fast asynchronous Scrapling fetcher (powered by curl_cffi)
                response = await AsyncFetcher.get(
                    url,
                    timeout=self.timeout,
                    headers=headers,
                )

                duration_ms = round((time.perf_counter() - fetch_start) * 1000, 2)
                status = response.status

                # Check if transient server error (500, 502, 503, 504, 429)
                if status in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    backoff = (2 ** attempt) + random.uniform(0.1, 0.4)
                    logger.warning(
                        "HTTP %d fetching %s (attempt %d/%d). Retrying in %.2fs...",
                        status, url, attempt + 1, self.max_retries, backoff
                    )
                    await asyncio.sleep(backoff)
                    continue

                html_content = getattr(response, "html_content", "") or ""
                if not html_content and hasattr(response, "body") and response.body:
                    encoding = getattr(response, "encoding", "utf-8") or "utf-8"
                    html_content = response.body.decode(encoding, errors="replace")
                final_url = str(response.url) if response.url else url

                # 2. Check for empty client-rendered dynamic shell if fallback enabled
                if self.enable_dynamic_fallback and self._needs_dynamic_render(html_content, status):
                    logger.info("Static page for %s appears empty or dynamic. Attempting DynamicFetcher...", url)
                    dynamic_result = await self._fetch_dynamic(url)
                    if dynamic_result and dynamic_result.status_code == 200:
                        return dynamic_result

                return FetchResult(
                    url=url,
                    final_url=final_url,
                    status_code=status,
                    content=html_content,
                    response_time_ms=duration_ms,
                    is_dynamic=False,
                    headers={k: str(v) for k, v in response.headers.items()} if hasattr(response, "headers") else {},
                )

            except Exception as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "Error fetching %s: %s (attempt %d/%d). Retrying in %.2fs...",
                        url, exc, attempt + 1, self.max_retries, backoff
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error("Exhausted retries fetching %s: %s", url, exc)

        total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return FetchResult(
            url=url,
            final_url=url,
            status_code=0,
            content="",
            response_time_ms=total_duration_ms,
            is_dynamic=False,
            error=last_error or "Network failure / timeout",
        )

    def _needs_dynamic_render(self, html: str, status: int) -> bool:
        """Determines if a page is a JavaScript-only single page application."""
        if status != 200:
            return False
        clean = html.lower()
        if len(clean) < 800:
            if "<noscript>" in clean and ("javascript" in clean or "enable" in clean):
                return True
            if ('id="root"' in clean or 'id="app"' in clean) and "<p" not in clean and "<h1" not in clean:
                return True
        return False

    async def _fetch_dynamic(self, url: str) -> Optional[FetchResult]:
        """Controlled fallback to DynamicFetcher (Playwright/Patchright) when static HTML is empty."""
        try:
            start_time = time.perf_counter()
            dyn_resp = await DynamicFetcher.async_fetch(
                url,
                timeout=self.timeout * 1000,
                headless=True,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return FetchResult(
                url=url,
                final_url=str(dyn_resp.url) if dyn_resp.url else url,
                status_code=dyn_resp.status,
                content=dyn_resp.text or "",
                response_time_ms=duration_ms,
                is_dynamic=True,
            )
        except Exception as exc:
            logger.debug("DynamicFetcher fallback failed for %s: %s", url, exc)
            return None
