import pytest
from app.crawler.policies import (
    normalize_url,
    validate_ssrf_boundary,
    is_same_domain,
    is_crawlable_page,
    score_url_priority,
    extract_domain,
)


def test_normalize_url():
    # Adding scheme
    assert normalize_url("example.com") == "https://example.com/"
    # Lowercasing host
    assert normalize_url("HTTPS://EXAMPLE.COM/about") == "https://example.com/about"
    # Stripping fragment
    assert normalize_url("https://example.com/about#team") == "https://example.com/about"
    # Stripping tracking parameters
    assert normalize_url("https://example.com/?utm_source=google&ref=123&keep=true") == "https://example.com/?keep=true"
    # Normalizing trailing slash on paths
    assert normalize_url("https://example.com/contact/") == "https://example.com/contact"
    # Root path keeps slash
    assert normalize_url("https://example.com") == "https://example.com/"


def test_normalize_url_invalid():
    # Empty URL
    with pytest.raises(ValueError):
        normalize_url("")

    # Unsupported schemes
    with pytest.raises(ValueError, match="Unsupported scheme"):
        normalize_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="Unsupported scheme"):
        normalize_url("ftp://example.com")


def test_ssrf_boundary_validation():
    # Localhost
    safe, err = validate_ssrf_boundary("http://localhost/test")
    assert not safe
    assert "forbidden" in err.lower()

    # Loopback IP
    safe, err = validate_ssrf_boundary("http://127.0.0.1:8000")
    assert not safe
    assert "private/reserved" in err.lower()

    # Private IPv4 ranges
    safe, err = validate_ssrf_boundary("http://192.168.1.10/admin")
    assert not safe
    assert "private/reserved" in err.lower()

    safe, err = validate_ssrf_boundary("http://10.0.0.1/status")
    assert not safe
    assert "private/reserved" in err.lower()

    safe, err = validate_ssrf_boundary("http://172.16.0.1/")
    assert not safe
    assert "private/reserved" in err.lower()

    # Cloud metadata IP (AWS/GCP/Azure)
    safe, err = validate_ssrf_boundary("http://169.254.169.254/latest/meta-data/")
    assert not safe
    assert "private/reserved" in err.lower()

    # Public domain should be allowed
    safe, err = validate_ssrf_boundary("https://example.com")
    assert safe
    assert err is None


def test_domain_extraction_and_same_domain():
    assert extract_domain("https://example.com/page") == "example.com"
    assert extract_domain("https://sub.example.com:8080/page") == "sub.example.com"

    # Same domain matching
    assert is_same_domain("https://example.com/about", "example.com")
    assert is_same_domain("https://www.example.com/about", "example.com")
    assert is_same_domain("https://blog.example.com/article", "example.com")
    assert not is_same_domain("https://google.com", "example.com")


def test_crawlable_page_and_priority_scoring():
    # Non-crawlable paths
    assert not is_crawlable_page("https://example.com/docs/manual.pdf")
    assert not is_crawlable_page("https://example.com/login")
    assert not is_crawlable_page("https://example.com/cart")
    assert not is_crawlable_page("https://example.com/wp-admin")

    # Crawlable paths
    assert is_crawlable_page("https://example.com/about-us")
    assert is_crawlable_page("https://example.com/services")

    # Priority scoring
    homepage_score = score_url_priority("https://example.com/")
    about_score = score_url_priority("https://example.com/about-us")
    services_score = score_url_priority("https://example.com/services")
    pricing_score = score_url_priority("https://example.com/pricing")
    careers_score = score_url_priority("https://example.com/careers")
    random_score = score_url_priority("https://example.com/misc-news")

    assert homepage_score == 100
    assert about_score == 90
    assert services_score == 85
    assert pricing_score == 75
    assert careers_score == 65
    assert random_score == 10
    assert homepage_score > about_score > services_score > pricing_score > careers_score > random_score
