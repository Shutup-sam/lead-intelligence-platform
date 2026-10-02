import json
from typing import List, Dict, Any
from app.ai.models import ICPProfile

SYSTEM_PROMPT = """You are an elite B2B Sales Intelligence and Lead Qualification AI Analyst with an uncompromising commitment to factual evidence grounding.
Your mission is to evaluate crawled website content for a domain and determine its exact alignment with an Ideal Customer Profile (ICP).

CORE ANTI-HALLUCINATION & EVIDENCE GROUNDING PROTOCOL:
1. EVIDENCE-BASED ONLY (STRICT EVIDENCE-GROUNDING): Rely strictly on the supplied crawled website text and metadata. Every extracted company attribute must be grounded in crawled source content. Do NOT fabricate, hallucinate, or assume company metrics.
2. NO INVENTED ATTRIBUTES (ZERO TOLERANCE FOR FABRICATION):
   - NEVER invent employee count or company size. If headcount is not explicitly stated on the site, `estimated_company_size` MUST be "Unknown".
   - NEVER invent commercial products or services. If the site is an informational repository, quote collection, blog, or demo sandbox, `products_or_services` MUST be an empty list [].
   - NEVER invent a business model. If no pricing, subscription tiers, enterprise licensing, or commercial sales model is described, `business_model` MUST be "Unknown" or "Non-Commercial / Sandbox".
   - NEVER invent technology stack or platforms (e.g., PostgreSQL, React, AWS). Only list technologies explicitly mentioned in the page text, scripts, or metadata. If none are stated, `technology_signals` MUST be [].
   - NEVER invent headquarters, geography, or operating region if not stated. Return "Unknown".
   - NEVER invent target customer personas if not stated. Return "Unknown".
3. STRICT EVIDENCE TRACEABILITY & NO SYNTHETIC/PLACEHOLDER URLS:
   - Every `source_url` MUST be chosen exclusively from the ALLOWED EVIDENCE URLS list provided in the prompt.
   - NEVER invent URLs, placeholder URLs (such as example.com, test.com, or synthetic paths), or URLs not fetched for this crawl target.
   - Quoted `evidence` MUST be verbatim quotations of text that actually exists in the crawled content of the cited page.
4. PRECISE SCORING (0-100):
   - 80-100: Exceptional fit. Matches target industries, verified B2B software/service offering, target geography, with strong positive evidence.
   - 60-79: Strong fit. Minor gaps or unverified headcount, but clearly matching core offering and industry.
   - 40-59: Moderate / Unclear fit. Tangentially related, consulting rather than product, or ambiguous business model.
   - 0-39: Poor fit or Disqualified. Consumer B2C only, personal blog, educational demo sandbox, stock broking/retail financial services (when targeting B2B SaaS), or explicitly flagged negative signal.
5. CONFIDENCE SCORE (0.0 - 1.0):
   - Reflects completeness of crawled evidence. High confidence (0.8+) requires verified about/product/pricing pages or definitive negative evidence proving non-commercial status.
6. SEPARATION OF FACTS, INFERENCES, AND UNKNOWNS:
   - Observed Facts: Directly observed, verifiable statements with exact page citations.
   - Inferred Signals: Deductions derived with explicit reasoning, confidence (0.0 to 1.0), and evidence.
   - Unknown Information: Explicitly list all fields for which the crawler found zero evidence.
7. NEGATIVE EVIDENCE UTILIZATION:
   - If a target site is an informational demonstration, quotes collection, scraping sandbox, or personal blog, you MUST use the real negative evidence that actually exists to disqualify it (assigning an ICP score below 25).
8. JSON ONLY: Return strictly valid JSON adhering to the specified schema with no commentary or markdown wrappers outside the JSON.
"""


def build_qualification_user_prompt(
    domain: str,
    target_url: str,
    pages_data: List[Dict[str, Any]],
    icp_profile: ICPProfile,
    max_input_chars: int = 16000,
) -> str:
    """
    Constructs the detailed user prompt containing ICP criteria, crawled pages,
    and metadata while enforcing character budget constraints and strict grounding.
    """
    icp_section = json.dumps(
        {
            "target_industries": icp_profile.target_industries,
            "target_company_size": icp_profile.target_company_size,
            "target_geographies": icp_profile.target_geographies,
            "required_signals": icp_profile.required_signals,
            "negative_disqualifiers": icp_profile.negative_signals,
            "qualification_threshold": icp_profile.min_icp_threshold,
        },
        indent=2,
    )

    allowed_urls = [p.get("url") for p in pages_data if p.get("url")]
    allowed_urls_list_str = "\n".join([f"- {u}" for u in allowed_urls])

    pages_text_blocks = []
    current_char_count = 0

    for idx, page in enumerate(pages_data, 1):
        url = page.get("url", "")
        title = page.get("title") or "Untitled Page"
        markdown = page.get("content_markdown", "").strip()
        metadata = page.get("metadata", {})

        page_block = f"=== CRAWLED PAGE {idx} (ID: PAGE_{idx}) ===\nURL: {url}\nTitle: {title}\n"
        if metadata.get("description"):
            page_block += f"Meta Description: {metadata['description']}\n"
        if metadata.get("emails"):
            page_block += f"Emails Found: {', '.join(metadata['emails'])}\n"
        if metadata.get("phones"):
            page_block += f"Phones Found: {', '.join(metadata['phones'])}\n"
        if metadata.get("social_links"):
            page_block += f"Social Profiles: {json.dumps(metadata['social_links'])}\n"
        if metadata.get("json_ld"):
            page_block += f"Structured Data: {json.dumps(metadata['json_ld'])[:500]}\n"

        page_block += f"\nPAGE CONTENT (MARKDOWN):\n{markdown}\n\n"

        if current_char_count + len(page_block) > max_input_chars:
            remaining = max(0, max_input_chars - current_char_count)
            if remaining > 300:
                pages_text_blocks.append(page_block[:remaining] + "\n...[truncated for length]")
            break

        pages_text_blocks.append(page_block)
        current_char_count += len(page_block)

    all_pages_text = "".join(pages_text_blocks)

    return f"""Analyze the following business website and qualify it against the specified ICP using strict evidence-grounding.

=== TARGET WEBSITE ===
Domain: {domain}
Root URL: {target_url}

=== IDEAL CUSTOMER PROFILE (ICP) CRITERIA ===
{icp_section}

=== ALLOWED EVIDENCE URLS (CRITICAL: YOU MAY ONLY CITE URLS FROM THIS EXACT LIST) ===
{allowed_urls_list_str}

=== CRAWLED PAGES & EXTRACTED EVIDENCE ===
{all_pages_text}

=== GROUNDING & EVIDENCE INTEGRITY INSTRUCTIONS ===
1. Every "source_url" in "signals" and "grounded_attributes" MUST be chosen exclusively from the ALLOWED EVIDENCE URLS list above.
2. NEVER use example.com, placeholder URLs, synthetic URLs, or any URL not listed above. Any unlisted URL will be rejected as hallucination.
3. Every "evidence" snippet MUST be a verbatim quote of words that actually exist in the crawled content of that cited page.
4. If employee count/headcount is NOT explicitly stated in the text, set "estimated_company_size": "Unknown".
5. If the site does NOT sell or provide commercial products or services, set "products_or_services": [].
6. If no commercial business model is stated, set "business_model": "Unknown" or "Non-Commercial / Sandbox".
7. If technologies are NOT explicitly stated in the text, set "technology_signals": [].
8. If geography/headquarters is NOT stated in the text, set "geography": "Unknown".
9. In "unknown_attributes", explicitly list all attributes where evidence was absent.

=== REQUIRED JSON OUTPUT FORMAT ===
Produce a single JSON object with the following schema:
{{
  "company_name": "string (official name or domain)",
  "company_summary": "string (2-3 sentences based strictly on crawled pages)",
  "value_proposition": "string (core value proposition, or 'Unknown / None' if non-commercial)",
  "industry": "string (e.g. 'Publishing / Quote Sandbox' or 'Unknown')",
  "target_audience": "string (or 'Unknown')",
  "products_or_services": ["string"] (must be [] if none verified),
  "business_model": "string (e.g. 'Unknown / Non-Commercial' or 'B2B Subscription')",
  "geography": "string (or 'Unknown')",
  "estimated_company_size": "string ('1-10', '11-50', '51-200', '201-500', '500+', or 'Unknown')",
  "technology_signals": ["string"] (must be [] if none explicitly named),
  "contact_signals": {{ "emails": ["..."], "phones": ["..."], "addresses": ["..."] }},
  "icp_score": int (0 to 100),
  "confidence_score": float (0.0 to 1.0),
  "positive_signals": ["string"],
  "negative_signals": ["string"],
  "qualification_reasoning": "string (detailed explanation based on evidence)",
  "signals": [
    {{
      "signal": "string",
      "evidence": "string (verbatim quote or factual observation)",
      "source_url": "string or null",
      "sentiment": "positive | negative | neutral",
      "status": "observed | inferred | unknown",
      "confidence": float (0.0 to 1.0)
    }}
  ],
  "observed_facts": ["string with citation"],
  "inferred_signals": ["string with reasoning and confidence"],
  "unknown_attributes": ["string (e.g. 'estimated_company_size', 'products_or_services', 'business_model')"],
  "grounded_attributes": {{
    "company_size": {{
      "value": "string or null",
      "status": "observed | inferred | unknown",
      "confidence": float,
      "evidence": "string or null",
      "source_url": "string or null"
    }},
    "business_model": {{
      "value": "string or null",
      "status": "observed | inferred | unknown",
      "confidence": float,
      "evidence": "string or null",
      "source_url": "string or null"
    }},
    "products_or_services": {{
      "value": "string or null",
      "status": "observed | inferred | unknown",
      "confidence": float,
      "evidence": "string or null",
      "source_url": "string or null"
    }},
    "geography": {{
      "value": "string or null",
      "status": "observed | inferred | unknown",
      "confidence": float,
      "evidence": "string or null",
      "source_url": "string or null"
    }},
    "technology_signals": {{
      "value": "string or null",
      "status": "observed | inferred | unknown",
      "confidence": float,
      "evidence": "string or null",
      "source_url": "string or null"
    }}
  }}
}}
"""
