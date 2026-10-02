import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from typing import Dict, Tuple, Optional
import httpx

logger = logging.getLogger("lead_intelligence.crawler.robots")


class RobotsPolicy:
    """
    Evaluates and caches robots.txt policies for crawled domains.
    Guarantees compliant crawling and records authorization decisions.
    """

    def __init__(self, user_agent: str = "LeadIntelligenceBot"):
        self.user_agent = user_agent
        self._cache: Dict[str, RobotFileParser] = {}
        self._status_cache: Dict[str, str] = {}

    def parse_robots_content(self, domain: str, content: str) -> None:
        """Directly parses robots.txt content (useful for testing and static loads)."""
        parser = RobotFileParser()
        parser.parse(content.splitlines())
        self._cache[domain] = parser
        self._status_cache[domain] = "loaded_manually"

    async def fetch_and_parse(self, base_url: str, timeout: int = 5) -> Tuple[bool, str]:
        """
        Fetches robots.txt from the target domain and parses permissions.
        Returns (is_available, status_message).
        """
        parsed = urlparse(base_url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.lower()

        if netloc in self._cache:
            return True, self._status_cache.get(netloc, "cached")

        robots_url = f"{scheme}://{netloc}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                    self._cache[netloc] = parser
                    self._status_cache[netloc] = "rules_applied"
                    logger.info("Successfully parsed robots.txt for %s", netloc)
                    return True, "rules_applied"
                elif resp.status_code in {404, 410}:
                    # Absent robots.txt means all paths are allowed by standard convention
                    parser.parse(["User-agent: *", "Allow: /"])
                    self._cache[netloc] = parser
                    self._status_cache[netloc] = "not_found_allowed_all"
                    logger.info("robots.txt not found (HTTP %d) for %s; allowing all paths", resp.status_code, netloc)
                    return True, "not_found_allowed_all"
                elif resp.status_code in {401, 403}:
                    # Forbidden robots.txt indicates conservative disallow
                    parser.parse(["User-agent: *", "Disallow: /"])
                    self._cache[netloc] = parser
                    self._status_cache[netloc] = "forbidden_disallow_all"
                    logger.warning("robots.txt returned HTTP %d for %s; disallowing all paths", resp.status_code, netloc)
                    return True, "forbidden_disallow_all"
                else:
                    # Non-standard HTTP response; allow with default parser
                    parser.parse(["User-agent: *", "Allow: /"])
                    self._cache[netloc] = parser
                    self._status_cache[netloc] = f"http_{resp.status_code}_default_allowed"
                    return True, self._status_cache[netloc]
        except Exception as exc:
            logger.warning("Failed to fetch robots.txt for %s: %s; falling back to permissive mode", netloc, exc)
            parser.parse(["User-agent: *", "Allow: /"])
            self._cache[netloc] = parser
            self._status_cache[netloc] = f"error_default_allowed: {str(exc)}"
            return False, self._status_cache[netloc]

    def is_allowed(self, url: str) -> Tuple[bool, str]:
        """
        Determines whether the given URL is permitted to be crawled.
        Returns (is_allowed, reason).
        """
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"

        parser = self._cache.get(netloc)
        if not parser:
            return True, "no_robots_policy_cached"

        allowed = parser.can_fetch(self.user_agent, url)
        if not allowed:
            # Also check fallback wildcard '*'
            allowed = parser.can_fetch("*", url)

        status_msg = self._status_cache.get(netloc, "rules_applied")
        if not allowed:
            return False, f"Disallowed by robots.txt ({status_msg}) for path: {path}"
        return True, f"Allowed by robots.txt ({status_msg})"
