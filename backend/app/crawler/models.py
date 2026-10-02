import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, HttpUrl


class CrawlRequest(BaseModel):
    """Input payload for requesting a website crawl."""
    url: str = Field(..., description="Target business website URL (e.g. https://example.com)")
    max_pages: Optional[int] = Field(None, ge=1, le=20, description="Max pages to crawl (default 6)")
    max_depth: Optional[int] = Field(None, ge=0, le=4, description="Max traversal depth (default 2)")
    delay_seconds: Optional[float] = Field(None, ge=0.1, le=10.0, description="Politeness delay between requests")
    timeout_seconds: Optional[int] = Field(None, ge=3, le=60, description="Request timeout in seconds")


class CrawlPageResult(BaseModel):
    """Structured result for a single crawled webpage."""
    url: str
    final_url: str
    status_code: int
    depth: int
    title: Optional[str] = None
    description: Optional[str] = None
    canonical_url: Optional[str] = None
    language: Optional[str] = None
    content_markdown: str = ""
    content_hash: str = ""
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    addresses: List[str] = Field(default_factory=list)
    internal_links: List[str] = Field(default_factory=list)
    external_links: List[str] = Field(default_factory=list)
    social_links: Dict[str, str] = Field(default_factory=dict)
    json_ld: List[Dict[str, Any]] = Field(default_factory=list)
    open_graph: Dict[str, str] = Field(default_factory=dict)
    response_time_ms: Optional[float] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CrawlSummaryResult(BaseModel):
    """Consolidated summary for a website crawl operation."""
    target_id: Optional[str] = None
    target_url: str
    normalized_url: str
    domain: str
    status: str  # "completed", "failed", "blocked_by_robots", "ssrf_rejected"
    pages_discovered: int = 0
    pages_crawled: int = 0
    pages_failed: int = 0
    emails_found: int = 0
    phones_found: int = 0
    duration_seconds: float = 0.0
    robots_status: str = "allowed"
    error_message: Optional[str] = None
    crawled_pages: List[CrawlPageResult] = Field(default_factory=list)
