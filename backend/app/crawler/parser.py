import hashlib
import re
from typing import Tuple
from bs4 import BeautifulSoup
import markdownify

# Tags completely removed from content before Markdown conversion
BOILERPLATE_TAGS = [
    "script", "style", "noscript", "iframe", "svg", "canvas",
    "nav", "header", "footer", "aside", "form", "button", "dialog"
]

# Attribute keywords commonly used for cookie banners, popups, and consent dialogs
BOILERPLATE_ATTR_KEYWORDS = [
    "cookie", "consent", "gdpr", "banner", "popup", "modal", "overlay",
    "advertisement", "ad-container", "promo", "newsletter", "subscribe"
]


def clean_html_to_markdown(html_content: str) -> Tuple[str, str]:
    """
    Sanitizes raw HTML to extract meaningful business copy:
    - Strips scripts, styles, navigation, headers, footers, and cookie banners
    - Converts structured DOM to clean Markdown (ATX headers, lists, paragraphs)
    - Returns (clean_markdown, sha256_content_hash)
    """
    if not html_content or not html_content.strip():
        return "", hashlib.sha256(b"").hexdigest()

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Remove head and boilerplate structural tags
        if soup.head:
            soup.head.decompose()

        for tag in soup.find_all(BOILERPLATE_TAGS):
            tag.decompose()

        # 2. Remove elements with IDs or classes indicating banners, popups, or cookies
        for element in soup.find_all(attrs=True):
            # Check ID
            elem_id = str(element.get("id", "")).lower()
            if any(kw in elem_id for kw in BOILERPLATE_ATTR_KEYWORDS):
                element.decompose()
                continue

            # Check classes
            classes = element.get("class", [])
            class_str = " ".join(classes).lower() if isinstance(classes, list) else str(classes).lower()
            if any(kw in class_str for kw in BOILERPLATE_ATTR_KEYWORDS):
                element.decompose()
                continue

            # Check ARIA roles
            role = str(element.get("role", "")).lower()
            if role in {"banner", "dialog", "alertdialog", "navigation"}:
                element.decompose()
                continue

        # 3. Convert the cleaned body or tree to Markdown
        body_or_root = soup.body or soup
        raw_markdown = markdownify.markdownify(
            str(body_or_root),
            heading_style="ATX",
            bullets="*",
            strip=["img", "input", "button", "select", "option", "textarea"],
        )

        # 4. Normalize whitespace and empty lines
        lines = [line.strip() for line in raw_markdown.splitlines()]
        # Collapse multiple blank lines
        clean_lines = []
        for line in lines:
            if line:
                clean_lines.append(line)
            elif clean_lines and clean_lines[-1] != "":
                clean_lines.append("")

        clean_markdown = "\n".join(clean_lines).strip()
        content_hash = hashlib.sha256(clean_markdown.encode("utf-8")).hexdigest()

        return clean_markdown, content_hash

    except Exception:
        # Fallback to basic regex-based stripping in worst case
        text = re.sub(r"<[^>]+>", " ", html_content)
        cleaned = re.sub(r"\s+", " ", text).strip()
        h = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        return cleaned, h
