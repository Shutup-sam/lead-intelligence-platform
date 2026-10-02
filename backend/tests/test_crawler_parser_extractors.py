import pytest
from bs4 import BeautifulSoup
from app.crawler.parser import clean_html_to_markdown
from app.crawler.extractors import (
    extract_page_metadata,
    extract_contact_info,
    extract_links,
    extract_json_ld,
)

SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Apex Dynamics | Autonomous Supply Chain Intelligence</title>
    <meta name="description" content="AI platform transforming global enterprise supply chains.">
    <link rel="canonical" href="https://apexdynamics.ai/solutions">
    <meta property="og:title" content="Apex Dynamics Official">
    <meta property="og:description" content="Enterprise logistics intelligence.">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Corporation",
        "name": "Apex Dynamics AI",
        "url": "https://apexdynamics.ai",
        "telephone": "+1-800-555-0199",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "100 Innovation Way, Suite 400",
            "addressLocality": "San Francisco",
            "addressRegion": "CA",
            "postalCode": "94105",
            "addressCountry": "US"
        }
    }
    </script>
    <style>.banner { background: #000; }</style>
</head>
<body>
    <nav>
        <a href="/">Home</a>
        <a href="/about">About Us</a>
        <a href="/pricing">Pricing</a>
    </nav>
    <div id="cookie-consent-banner" class="cookie-modal">
        <p>We use cookies to enhance your experience. <button>Accept All</button></p>
    </div>

    <main>
        <h1>Autonomous Supply Chain Solutions</h1>
        <p>Apex Dynamics helps global distributors predict disruptions with 98% accuracy.</p>

        <h2>Core Capabilities</h2>
        <ul>
            <li>Predictive inventory rebalancing</li>
            <li>Real-time tariff impact modeling</li>
            <li>Autonomous carrier procurement</li>
        </ul>

        <div class="contact-section">
            <p>Direct inquiries to our team: <a href="mailto:contact@apexdynamics.ai">contact@apexdynamics.ai</a> or call <a href="tel:+18005550199">+1 (800) 555-0199</a>.</p>
            <p>Our European office is reached at info.eu@apexdynamics.ai or +44 20 7946 0912.</p>
            <address>100 Innovation Way, Suite 400, San Francisco CA 94105</address>
        </div>
    </main>

    <footer>
        <p>&copy; 2026 Apex Dynamics Inc. All rights reserved.</p>
        <div class="socials">
            <a href="https://www.linkedin.com/company/apex-dynamics-ai">LinkedIn</a>
            <a href="https://twitter.com/apexdynamics">Twitter</a>
            <a href="https://github.com/apexdynamics">GitHub</a>
            <a href="https://externalsite.org/partner">External Partner</a>
        </div>
    </footer>
</body>
</html>
"""


def test_clean_html_to_markdown():
    markdown, content_hash = clean_html_to_markdown(SAMPLE_HTML)

    # Key business contents preserved
    assert "# Autonomous Supply Chain Solutions" in markdown
    assert "## Core Capabilities" in markdown
    assert "Predictive inventory rebalancing" in markdown
    assert "Autonomous carrier procurement" in markdown

    # Boilerplate removed
    assert "cookie" not in markdown.lower()
    assert "Accept All" not in markdown
    assert "<nav>" not in markdown
    assert "<style>" not in markdown

    # Deterministic hash generated
    assert len(content_hash) == 64
    assert isinstance(content_hash, str)


def test_extract_page_metadata():
    soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
    meta = extract_page_metadata(soup)

    assert meta["title"] == "Apex Dynamics | Autonomous Supply Chain Intelligence"
    assert meta["description"] == "AI platform transforming global enterprise supply chains."
    assert meta["canonical_url"] == "https://apexdynamics.ai/solutions"
    assert meta["language"] == "en"
    assert meta["open_graph"].get("og:title") == "Apex Dynamics Official"


def test_extract_contact_info():
    soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
    contacts = extract_contact_info(soup, SAMPLE_HTML)

    assert "contact@apexdynamics.ai" in contacts["emails"]
    assert "info.eu@apexdynamics.ai" in contacts["emails"]

    assert any("800" in p for p in contacts["phones"])
    assert len(contacts["addresses"]) >= 1
    assert any("Innovation Way" in a for a in contacts["addresses"])


def test_extract_links():
    soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
    internal, external, socials = extract_links(
        soup, current_url="https://apexdynamics.ai/", base_domain="apexdynamics.ai"
    )

    # Internal links
    assert "https://apexdynamics.ai/about" in internal
    assert "https://apexdynamics.ai/pricing" in internal

    # External & social links
    assert "linkedin" in socials
    assert "https://www.linkedin.com/company/apex-dynamics-ai" == socials["linkedin"]
    assert "twitter" in socials
    assert "github" in socials
    assert "https://externalsite.org/partner" in external


def test_extract_json_ld():
    soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
    json_ld = extract_json_ld(soup)

    assert len(json_ld) == 1
    item = json_ld[0]
    assert item["@type"] == "Corporation"
    assert item["name"] == "Apex Dynamics AI"
    assert item["telephone"] == "+1-800-555-0199"
