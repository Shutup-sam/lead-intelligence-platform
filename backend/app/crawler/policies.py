import ipaddress
import re
import socket
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Tuple, Optional, Set

# Forbidden URL schemes
ALLOWED_SCHEMES = {"http", "https"}

# Disallowed file extensions for text content crawling
DISALLOWED_EXTENSIONS = {
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".bin",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".tiff",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".webm",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".css", ".js", ".json", ".xml", ".rss"
}

# Negative path segments indicating irrelevant/authentication/account areas
AVOID_PATH_PATTERNS = [
    r"/login", r"/signin", r"/sign-in", r"/signup", r"/sign-up", r"/register",
    r"/auth", r"/oauth", r"/password", r"/account", r"/dashboard", r"/admin",
    r"/cart", r"/checkout", r"/basket", r"/order", r"/pay", r"/billing",
    r"/terms", r"/privacy", r"/cookie", r"/legal", r"/disclaimer",
    r"/feed", r"/wp-admin", r"/wp-login", r"/wp-content", r"/cdn-cgi",
    r"/search\?", r"/tag/", r"/category/", r"/author/"
]

# Business priority keywords and relative scores
PRIORITY_KEYWORDS = {
    "about": 90,
    "about-us": 90,
    "company": 90,
    "who-we-are": 90,
    "mission": 85,
    "services": 85,
    "solutions": 85,
    "what-we-do": 85,
    "products": 80,
    "features": 80,
    "platform": 80,
    "technology": 80,
    "pricing": 75,
    "plans": 75,
    "contact": 70,
    "contact-us": 70,
    "get-in-touch": 70,
    "careers": 65,
    "jobs": 65,
    "team": 65,
}

# Tracking query parameters to strip
TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "source", "mc_cid", "mc_eid"
}


def normalize_url(raw_url: str) -> str:
    """
    Normalizes a URL:
    - Adds https:// if missing scheme
    - Converts host to lowercase
    - Strips fragment (#)
    - Strips tracking parameters
    - Normalizes trailing slash (retains root '/', removes from non-root paths)
    """
    cleaned = raw_url.strip()
    if not cleaned:
        raise ValueError("URL cannot be empty")

    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):(?://)?", cleaned)
    if scheme_match:
        scheme = scheme_match.group(1).lower()
        if scheme not in ALLOWED_SCHEMES:
            raise ValueError(f"Unsupported scheme '{scheme}'. Only http and https are allowed.")
        # Ensure standard '://' formatting
        rest = cleaned[scheme_match.end():]
        cleaned = f"{scheme}://{rest}"
    else:
        # Default to https
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL structure: {raw_url}")

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Unsupported scheme '{scheme}'. Only http and https are allowed.")

    # Strip default port if present
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Normalize path
    path = parsed.path or "/"
    # Clean multiple consecutive slashes
    path = re.sub(r"/+", "/", path)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Filter out tracking query params, sort remainder for determinism
    query = ""
    if parsed.query:
        query_dict = parse_qs(parsed.query, keep_blank_values=False)
        filtered_query = {
            k: v for k, v in query_dict.items() if k.lower() not in TRACKING_QUERY_PARAMS
        }
        if filtered_query:
            query = urlencode(filtered_query, doseq=True)

    # Reconstruct normalized URL without fragment
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def validate_ssrf_boundary(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validates that a URL does not point to localhost, private networks,
    link-local addresses, or cloud metadata services.
    Returns (is_safe, error_message).
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False, "Missing hostname in URL"

        # Explicit forbidden names
        lowered_host = hostname.lower()
        if lowered_host in {"localhost", "localhost.localdomain", "broadcasthost"} or \
           lowered_host.endswith((".local", ".localhost", ".internal", ".localdomain")):
            return False, f"Access to local hostname '{hostname}' is forbidden."

        # Check if hostname is directly an IP literal
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if _is_disallowed_ip(ip_obj):
                return False, f"Target IP '{hostname}' belongs to a private/reserved network."
            return True, None
        except ValueError:
            pass  # Not an IP literal, proceed to DNS resolution

        # Resolve hostname to verify destination IPs
        try:
            addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            for item in addr_info:
                sockaddr = item[4]
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if _is_disallowed_ip(ip_obj):
                    return False, f"Hostname '{hostname}' resolves to private/reserved IP {ip_str}."
        except socket.gaierror as e:
            return False, f"DNS resolution failed for '{hostname}': {str(e)}"

        return True, None
    except Exception as exc:
        return False, f"SSRF boundary check failed: {str(exc)}"


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Helper to detect private, loopback, link-local, or multicast IPs."""
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or str(ip) in {"169.254.169.254", "fe80::1"}  # AWS/GCP/Azure metadata IP
    )


def extract_domain(url: str) -> str:
    """Extracts root or fully qualified domain name from a URL."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    # Strip port if present
    if ":" in netloc:
        netloc = netloc.split(":")[0]
    return netloc


def is_same_domain(url: str, base_domain: str) -> bool:
    """
    Checks if a URL belongs to the same domain as base_domain
    (e.g., base_domain='example.com' matches 'example.com' and 'www.example.com').
    """
    target_domain = extract_domain(url)
    if target_domain == base_domain:
        return True

    # Strip 'www.' prefix for comparison
    clean_base = base_domain.removeprefix("www.")
    clean_target = target_domain.removeprefix("www.")
    return clean_target == clean_base or clean_target.endswith(f".{clean_base}")


def is_crawlable_page(url: str) -> bool:
    """Checks whether the URL path is eligible for content crawling."""
    parsed = urlparse(url)
    path = parsed.path.lower()

    # Reject unsupported non-HTML extensions
    for ext in DISALLOWED_EXTENSIONS:
        if path.endswith(ext):
            return False

    # Reject obvious negative path patterns
    for pattern in AVOID_PATH_PATTERNS:
        if re.search(pattern, path):
            return False

    return True


def score_url_priority(url: str) -> int:
    """
    Scores URL priority for business intelligence extraction (0 - 100).
    Higher scores are crawled first.
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/").lower()

    if not path:
        return 100  # Homepage is maximum priority

    # Check path segments against priority keywords
    segments = path.split("/")
    max_score = 10  # baseline score for any valid internal page

    for seg in segments:
        clean_seg = seg.split(".")[0]
        if clean_seg in PRIORITY_KEYWORDS:
            score = PRIORITY_KEYWORDS[clean_seg]
            if score > max_score:
                max_score = score

    return max_score
