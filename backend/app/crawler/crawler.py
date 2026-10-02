import asyncio
import logging
from typing import List, Set, Dict, Tuple, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from app.core.config import settings
from app.crawler.models import CrawlPageResult
from app.crawler.fetcher import ScraplingFetcher
from app.crawler.parser import clean_html_to_markdown
from app.crawler.robots import RobotsPolicy
from app.crawler.policies import (
    extract_domain,
    is_same_domain,
    is_crawlable_page,
    score_url_priority,
    normalize_url,
)
from app.crawler.extractors import (
    extract_page_metadata,
    extract_contact_info,
    extract_links,
    extract_json_ld,
)

logger = logging.getLogger("lead_intelligence.crawler.engine")


class WebsiteCrawler:
    """
    Orchestrates breadth-first search crawling over a single target domain.
    Enforces politeness, robots.txt authorization, deduplication, priority scoring,
    and deterministic metadata extraction.
    """

    def __init__(
        self,
        fetcher: Optional[ScraplingFetcher] = None,
        robots_policy: Optional[RobotsPolicy] = None,
        max_pages: int = settings.CRAWLER_MAX_PAGES,
        max_depth: int = settings.CRAWLER_MAX_DEPTH,
    ):
        self.fetcher = fetcher or ScraplingFetcher()
        self.robots_policy = robots_policy or RobotsPolicy()
        self.max_pages = max_pages
        self.max_depth = max_depth

    async def crawl_site(self, root_url: str) -> Tuple[List[CrawlPageResult], int, int]:
        """
        Crawls the target site starting from root_url.
        Returns (crawled_pages, total_discovered, total_failed).
        """
        normalized_root = normalize_url(root_url)
        base_domain = extract_domain(normalized_root)

        # 1. Fetch & evaluate robots.txt
        await self.robots_policy.fetch_and_parse(normalized_root)

        # State tracking
        visited_urls: Set[str] = set()
        seen_content_hashes: Set[str] = set()
        discovered_urls: Set[str] = {normalized_root}
        results: List[CrawlPageResult] = []
        failed_count = 0

        # Queue items: (priority_score, depth, url)
        # We start with the homepage at depth 0
        queue: List[Tuple[int, int, str]] = [
            (score_url_priority(normalized_root), 0, normalized_root)
        ]

        logger.info(
            "Starting crawl for domain %s (max_pages=%d, max_depth=%d)",
            base_domain, self.max_pages, self.max_depth
        )

        while queue and len(results) < self.max_pages:
            # Sort queue descending by priority score, ascending by depth
            queue.sort(key=lambda item: (-item[0], item[1]))
            score, depth, current_url = queue.pop(0)

            if current_url in visited_urls:
                continue
            visited_urls.add(current_url)

            # 2. Robots.txt evaluation
            is_allowed, robot_reason = self.robots_policy.is_allowed(current_url)
            if not is_allowed:
                logger.warning("Skipping %s: %s", current_url, robot_reason)
                continue

            logger.info("Crawling [depth %d, score %d]: %s", depth, score, current_url)

            # 3. Fetch webpage via ScraplingFetcher
            fetch_res = await self.fetcher.fetch(current_url)
            if fetch_res.status_code != 200 or not fetch_res.content:
                failed_count += 1
                logger.warning(
                    "Fetch failed for %s (Status: %d, Error: %s)",
                    current_url, fetch_res.status_code, fetch_res.error
                )
                continue

            # 4. Clean HTML to Markdown & generate content hash
            content_markdown, content_hash = clean_html_to_markdown(fetch_res.content)

            # Skip duplicate page bodies (e.g. redirected or identical template shells)
            if content_hash in seen_content_hashes and len(content_markdown) > 50:
                logger.debug("Duplicate content detected for %s (hash %s); skipping duplicate", current_url, content_hash[:8])
                continue
            seen_content_hashes.add(content_hash)

            # 5. Extract deterministic metadata
            soup = BeautifulSoup(fetch_res.content, "html.parser")
            meta = extract_page_metadata(soup)
            contacts = extract_contact_info(soup, fetch_res.content)
            internal_links, external_links, social_links = extract_links(
                soup, fetch_res.final_url, base_domain
            )
            json_ld = extract_json_ld(soup)

            page_result = CrawlPageResult(
                url=current_url,
                final_url=fetch_res.final_url,
                status_code=fetch_res.status_code,
                depth=depth,
                title=meta["title"],
                description=meta["description"],
                canonical_url=meta["canonical_url"],
                language=meta["language"],
                content_markdown=content_markdown,
                content_hash=content_hash,
                emails=contacts["emails"],
                phones=contacts["phones"],
                addresses=contacts["addresses"],
                internal_links=internal_links,
                external_links=external_links,
                social_links=social_links,
                json_ld=json_ld,
                open_graph=meta["open_graph"],
                response_time_ms=fetch_res.response_time_ms,
            )
            results.append(page_result)

            # 6. Enqueue internal links for subsequent BFS depth if within max_depth
            if depth < self.max_depth:
                for link in internal_links:
                    discovered_urls.add(link)
                    if link not in visited_urls and all(link != q[2] for q in queue):
                        link_score = score_url_priority(link)
                        queue.append((link_score, depth + 1, link))

        logger.info(
            "Crawl completed for %s: %d pages crawled, %d discovered, %d failed",
            base_domain, len(results), len(discovered_urls), failed_count
        )

        return results, len(discovered_urls), failed_count
