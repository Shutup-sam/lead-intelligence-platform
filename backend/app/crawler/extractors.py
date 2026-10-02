import json
import logging
import re
from typing import Dict, Any, List, Set, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from app.crawler.policies import (
    is_same_domain,
    is_crawlable_page,
    normalize_url,
    extract_domain,
)

logger = logging.getLogger("lead_intelligence.crawler.extractors")

# Email regex pattern
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Common fake/placeholder email domains and file extension false-positives
EXCLUDED_EMAIL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js"}
EXCLUDED_EMAIL_HOSTS = {"example.com", "domain.com", "yoursite.com", "yourdomain.com", "email.com"}

# Phone regex pattern (US, International, and dashed/parenthetical formats)
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"
)

# Social media domains to classify
SOCIAL_PLATFORMS = {
    "linkedin": [r"linkedin\.com/(?:company|in|school)/"],
    "twitter": [r"twitter\.com/", r"x\.com/"],
    "facebook": [r"facebook\.com/"],
    "instagram": [r"instagram\.com/"],
    "youtube": [r"youtube\.com/(?:channel|c|user|@)"],
    "github": [r"github\.com/"],
}

# Relevant JSON-LD types for lead qualification
DESIRED_JSONLD_TYPES = {
    "organization", "localbusiness", "corporation", "person",
    "product", "service", "website", "company", "store"
}


def extract_page_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extracts title, meta description, canonical, language, and OpenGraph data."""
    # Title
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("meta", property="og:title"):
        title = soup.find("meta", property="og:title").get("content", "").strip() or None

    # Meta Description
    description = None
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag["content"].strip()
    elif soup.find("meta", property="og:description"):
        description = soup.find("meta", property="og:description").get("content", "").strip() or None

    # Canonical URL
    canonical_url = None
    canonical_tag = soup.find("link", rel=re.compile(r"^canonical$", re.I))
    if canonical_tag and canonical_tag.get("href"):
        canonical_url = canonical_tag["href"].strip()

    # Language
    language = None
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        language = html_tag["lang"].strip()

    # OpenGraph Tags
    open_graph: Dict[str, str] = {}
    for meta in soup.find_all("meta", property=re.compile(r"^og:", re.I)):
        prop = meta.get("property", "").lower()
        content = meta.get("content", "").strip()
        if prop and content:
            open_graph[prop] = content

    return {
        "title": title,
        "description": description,
        "canonical_url": canonical_url,
        "language": language,
        "open_graph": open_graph,
    }


def extract_contact_info(soup: BeautifulSoup, text_content: str) -> Dict[str, List[str]]:
    """
    Extracts business contact information:
    - Emails (from mailto: links and high-confidence text regex)
    - Phone numbers (from tel: links and phone regex)
    - Physical addresses (from <address> tags and keyword patterns)
    """
    emails: Set[str] = set()
    phones: Set[str] = set()
    addresses: Set[str] = set()

    # 1. Inspect explicit mailto: links
    for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
        href = a["href"].strip()
        email = href.split(":", 1)[1].split("?")[0].strip()
        if _is_valid_email(email):
            emails.add(email.lower())

    # 2. Inspect text for emails
    for match in EMAIL_REGEX.finditer(text_content):
        email = match.group(0).strip()
        if _is_valid_email(email):
            emails.add(email.lower())

    # 3. Inspect explicit tel: links
    for a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
        href = a["href"].strip()
        raw_phone = href.split(":", 1)[1].split("?")[0].strip()
        clean_phone = re.sub(r"[^\d+]", "", raw_phone)
        if len(clean_phone) >= 7:
            phones.add(raw_phone)

    # 4. Inspect text for phone numbers
    for match in PHONE_REGEX.finditer(text_content):
        phone = match.group(0).strip()
        digits = re.sub(r"\D", "", phone)
        # Avoid dates like 2026-10-02 or short codes
        if 7 <= len(digits) <= 15:
            if not re.match(r"^(19|20)\d{2}[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])$", phone):
                phones.add(phone)

    # 5. Inspect <address> tags
    for addr in soup.find_all("address"):
        text = addr.get_text(separator=" ", strip=True)
        if text and len(text) > 10:
            addresses.add(text)

    # 6. Regex for US/International street addresses
    address_pattern = re.compile(
        r"\b\d{1,5}\s+[A-Za-z0-9\s.,#]{3,50}\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Suite|Ste|Floor|Fl)\b(?:[A-Za-z0-9\s.,#]{0,30}\b[A-Z]{2}\b\s+\d{5}(?:-\d{4})?)?",
        re.I
    )
    for match in address_pattern.finditer(text_content):
        addr = match.group(0).strip()
        if len(addr) > 12:
            addresses.add(addr)

    return {
        "emails": sorted(list(emails)),
        "phones": sorted(list(phones)),
        "addresses": sorted(list(addresses)),
    }


def _is_valid_email(email: str) -> bool:
    """Filters out common false positive emails."""
    if not email or "@" not in email:
        return False
    # Check forbidden extensions in username/domain
    lowered = email.lower()
    for ext in EXCLUDED_EMAIL_EXTENSIONS:
        if lowered.endswith(ext):
            return False
    parts = lowered.split("@")
    if len(parts) != 2:
        return False
    domain = parts[1]
    if domain in EXCLUDED_EMAIL_HOSTS or domain.endswith((".png", ".jpg", ".svg", ".webp")):
        return False
    if len(parts[0]) < 2 or len(parts[1]) < 4:
        return False
    return True


def extract_links(
    soup: BeautifulSoup, current_url: str, base_domain: str
) -> Tuple[List[str], List[str], Dict[str, str]]:
    """
    Extracts:
    - Internal crawlable URLs within the same domain
    - External links
    - Categorized social media links (LinkedIn, Twitter/X, Facebook, Instagram, YouTube)
    """
    internal_links: Set[str] = set()
    external_links: Set[str] = set()
    social_links: Dict[str, str] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue

        # Resolve relative URLs
        absolute_url = urljoin(current_url, href)
        try:
            normalized = normalize_url(absolute_url)
        except Exception:
            continue

        # Check for social media platforms
        is_social = False
        for platform, patterns in SOCIAL_PLATFORMS.items():
            for pat in patterns:
                if re.search(pat, normalized, re.I):
                    if platform not in social_links:
                        social_links[platform] = normalized
                    is_social = True
                    break
            if is_social:
                break

        if is_social:
            external_links.add(normalized)
            continue

        # Distinguish internal vs external
        if is_same_domain(normalized, base_domain):
            if is_crawlable_page(normalized):
                internal_links.add(normalized)
        else:
            external_links.add(normalized)

    return (
        sorted(list(internal_links)),
        sorted(list(external_links)),
        social_links,
    )


def extract_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extracts structured JSON-LD entities (Organization, LocalBusiness, Corporation, etc.)
    without invoking an LLM.
    """
    structured_data: List[Dict[str, Any]] = []

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                # If @graph is present (common in WordPress/Yoast)
                if "@graph" in item and isinstance(item["@graph"], list):
                    for graph_item in item["@graph"]:
                        if isinstance(graph_item, dict):
                            _maybe_append_jsonld(graph_item, structured_data)
                else:
                    _maybe_append_jsonld(item, structured_data)
        except Exception as exc:
            logger.debug("Failed parsing JSON-LD script block: %s", exc)

    return structured_data


def _maybe_append_jsonld(item: Dict[str, Any], target_list: List[Dict[str, Any]]) -> None:
    """Appends relevant business/entity JSON-LD objects."""
    item_type = str(item.get("@type", "")).lower()
    # Check if item type matches desired business entities
    if any(desired in item_type for desired in DESIRED_JSONLD_TYPES) or not item_type:
        target_list.append(item)
