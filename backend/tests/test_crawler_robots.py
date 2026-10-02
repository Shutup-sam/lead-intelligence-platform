import pytest
from app.crawler.robots import RobotsPolicy


def test_robots_allowed_and_disallowed_paths():
    policy = RobotsPolicy(user_agent="LeadIntelligenceBot")

    sample_robots_txt = """
User-agent: *
Disallow: /admin/
Disallow: /private/
Disallow: /checkout
Allow: /admin/public/

User-agent: Googlebot
Disallow: /google-only-block/
"""
    policy.parse_robots_content("example.com", sample_robots_txt)

    # Allowed paths
    allowed, reason = policy.is_allowed("https://example.com/")
    assert allowed
    assert "Allowed by robots.txt" in reason

    allowed, reason = policy.is_allowed("https://example.com/about")
    assert allowed

    allowed, reason = policy.is_allowed("https://example.com/services")
    assert allowed

    # Disallowed paths
    allowed, reason = policy.is_allowed("https://example.com/admin/settings")
    assert not allowed
    assert "Disallowed by robots.txt" in reason

    allowed, reason = policy.is_allowed("https://example.com/private/data")
    assert not allowed

    allowed, reason = policy.is_allowed("https://example.com/checkout")
    assert not allowed


@pytest.mark.asyncio
async def test_robots_fallback_permissive():
    policy = RobotsPolicy()
    # Unknown domain with no cached policy defaults safely
    allowed, reason = policy.is_allowed("https://unseen-domain.com/page")
    assert allowed
