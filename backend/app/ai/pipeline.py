import re
import logging
from typing import List, Dict, Any, Tuple, Optional

from app.core.config import settings
from app.crawler.policies import normalize_url, is_same_domain
from app.ai.models import CompanyQualification, ICPProfile
from app.ai.prompt import SYSTEM_PROMPT, build_qualification_user_prompt
from app.ai.llm_provider import BaseLLMProvider, LLMExecutionResult, get_llm_provider
from app.ai.embeddings import (
    BaseEmbeddingProvider,
    get_embedding_provider,
    build_canonical_embedding_document,
    compute_content_hash,
)

logger = logging.getLogger("lead_intelligence.ai.pipeline")


class QualificationPipeline:
    """
    Coordinates the AI qualification workflow:
    1. Selects and ranks crawled content
    2. Builds structured evidence prompts
    3. Invokes LLM with strict Pydantic validation
    4. Validates and sanitizes evidence grounding against crawled pages
    5. Generates canonical embedding document
    6. Computes dense vector embeddings
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        max_input_chars: int = settings.LLM_MAX_INPUT_CHARS,
    ):
        self.llm_provider = llm_provider or get_llm_provider()
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.max_input_chars = max_input_chars

    async def qualify(
        self,
        domain: str,
        target_url: str,
        crawled_pages: List[Dict[str, Any]],
        icp_profile: Optional[ICPProfile] = None,
    ) -> Tuple[CompanyQualification, str, str, List[float], LLMExecutionResult]:
        if not crawled_pages:
            raise ValueError(f"No crawled pages available for domain '{domain}'. Cannot qualify empty target.")

        active_icp = icp_profile or ICPProfile()

        # 1. Content selection & deduplication
        selected_pages = self._select_content(crawled_pages)

        # 2. Build prompt
        user_prompt = build_qualification_user_prompt(
            domain=domain,
            target_url=target_url,
            pages_data=selected_pages,
            icp_profile=active_icp,
            max_input_chars=self.max_input_chars,
        )

        logger.info(
            "Invoking LLM qualification for %s (%d pages selected, prompt length: %d chars)",
            domain, len(selected_pages), len(user_prompt)
        )

        # 3. Call LLM
        exec_result = await self.llm_provider.generate_qualification(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # 4. Validate output with strict Pydantic model
        try:
            qualification = CompanyQualification.model_validate(exec_result.data)
        except Exception as exc:
            logger.error("LLM structured output validation failed for %s: %s", domain, exc)
            raise ValueError(f"Invalid LLM qualification output schema: {str(exc)}") from exc

        # 4b. Enforce strict evidence integrity validation (URL & quote checking against crawled pages)
        qualification = self._validate_and_sanitize_evidence(qualification, domain, crawled_pages)

        # 4c. Enforce sandbox/demo disqualification rules
        qualification = self._enforce_evidence_grounding(qualification, crawled_pages)

        # 5. Build canonical document and hash for embedding
        canonical_doc = build_canonical_embedding_document(qualification)
        embedding_hash = compute_content_hash(canonical_doc)

        # 6. Generate embedding
        embedding_vector = await self.embedding_provider.generate_embedding(canonical_doc)

        return qualification, canonical_doc, embedding_hash, embedding_vector, exec_result

    def _validate_and_sanitize_evidence(
        self, qual: CompanyQualification, domain: str, pages: List[Dict[str, Any]]
    ) -> CompanyQualification:
        """
        Strict Evidence Integrity Validator:
        1. All evidence source URLs MUST match actual pages crawled for this target.
        2. All evidence source URLs MUST belong to the target domain/subdomains (no cross-domain).
        3. All quoted evidence snippets MUST actually exist in the crawled content of the cited page.
        4. If evidence is invalid or ungrounded, it is discarded, and corresponding claims are reset to Unknown.
        """
        # Map of crawled pages by normalized URL and raw URL
        crawled_urls: Dict[str, Dict[str, Any]] = {}
        for p in pages:
            raw_u = p.get("url", "").strip()
            final_u = p.get("final_url", "").strip()
            if raw_u:
                try:
                    crawled_urls[normalize_url(raw_u)] = p
                except Exception:
                    pass
                crawled_urls[raw_u.lower().rstrip("/")] = p
                crawled_urls[raw_u] = p
            if final_u:
                try:
                    crawled_urls[normalize_url(final_u)] = p
                except Exception:
                    pass
                crawled_urls[final_u.lower().rstrip("/")] = p
                crawled_urls[final_u] = p

        def quote_exists_in_page(quote: Optional[str], page_dict: Dict[str, Any]) -> bool:
            if not quote or not quote.strip():
                return False
            page_text = (
                f"{page_dict.get('title') or ''} "
                f"{page_dict.get('content_markdown') or ''} "
                f"{str(page_dict.get('metadata') or '')}"
            )
            q = quote.strip()
            if (q.startswith('"') and q.endswith('"')) or (q.startswith("'") and q.endswith("'")):
                q = q[1:-1].strip()

            # Exact substring
            if q.lower() in page_text.lower():
                return True

            # Normalized whitespace and stripped punctuation
            norm_q = re.sub(r'[*_#`"\'\(\)\[\]:,.-]', ' ', q.lower())
            norm_q = re.sub(r'\s+', ' ', norm_q).strip()
            norm_page = re.sub(r'[*_#`"\'\(\)\[\]:,.-]', ' ', page_text.lower())
            norm_page = re.sub(r'\s+', ' ', norm_page).strip()
            if norm_q and norm_q in norm_page:
                return True

            # Multi-word phrase check (consecutive 4-word windows)
            words = norm_q.split(' ')
            if len(words) >= 4:
                for i in range(len(words) - 3):
                    segment = " ".join(words[i:i+4])
                    if len(segment) >= 20 and segment in norm_page:
                        return True
            return False

        def verify_evidence_url(url: Optional[str]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
            if not url or not url.strip():
                return False, None, "Missing source URL"
            u = url.strip()
            # 1. Reject cross-domain
            if not is_same_domain(u, domain):
                return False, None, f"Cross-domain evidence rejected: '{u}' does not match target domain '{domain}'"

            # 2. Check if URL was among crawled pages
            matched_p = None
            try:
                matched_p = crawled_urls.get(normalize_url(u))
            except Exception:
                pass
            if not matched_p:
                matched_p = crawled_urls.get(u.lower().rstrip("/")) or crawled_urls.get(u)

            if not matched_p:
                return False, None, f"Un-crawled URL rejected: '{u}' was not fetched for this target"

            return True, matched_p, "Valid"

        # 1. Validate qual.signals
        valid_signals = []
        for sig in qual.signals:
            if sig.status == "unknown" and not sig.source_url:
                valid_signals.append(sig)
                continue

            is_valid_u, matched_p, reason = verify_evidence_url(sig.source_url)
            if not is_valid_u:
                logger.warning("Rejecting invalid signal '%s': %s", sig.signal, reason)
                continue

            if not quote_exists_in_page(sig.evidence, matched_p):
                logger.warning(
                    "Rejecting signal '%s': evidence quote '%s' not present in crawled page '%s'",
                    sig.signal, sig.evidence[:60], sig.source_url
                )
                continue

            valid_signals.append(sig)
        qual.signals = valid_signals

        # 2. Validate qual.observed_facts
        valid_facts = []
        for fact in qual.observed_facts:
            url_match = re.search(r'https?://[^\s\)]+', fact)
            if url_match:
                fact_url = url_match.group(0).rstrip('.,;)]')
                is_valid_u, matched_p, reason = verify_evidence_url(fact_url)
                if not is_valid_u:
                    logger.warning("Rejecting observed fact with invalid URL '%s': %s", fact_url, reason)
                    continue
            valid_facts.append(fact)
        qual.observed_facts = valid_facts

        # 3. Validate qual.grounded_attributes
        for attr_name, field in list(qual.grounded_attributes.items()):
            if field.status in ("observed", "inferred") and field.source_url:
                is_valid_u, matched_p, reason = verify_evidence_url(field.source_url)
                valid_q = is_valid_u and quote_exists_in_page(field.evidence, matched_p)
                if not is_valid_u or not valid_q:
                    logger.warning(
                        "Grounded attribute '%s' failed evidence verification (%s); degrading to unknown",
                        attr_name, reason if not is_valid_u else "quote not in crawled content"
                    )
                    field.status = "unknown"
                    field.confidence = 0.0
                    field.value = "Unknown"
                    field.evidence = f"Unverified claim rejected: evidence not substantiated by crawled content ({reason if not is_valid_u else 'quote not in page'})"
                    field.source_url = None

        # 4. Enforce grounding against combined crawl text
        combined_text = " ".join([
            f"{p.get('title', '')} {p.get('content_markdown', '')} {str(p.get('metadata', {}))}"
            for p in pages
        ]).lower()

        # Company size validation
        if qual.estimated_company_size != "Unknown":
            headcount_indicators = ["employee", "employees", "headcount", "staff", "team of", "workforce", "people"]
            if not any(k in combined_text for k in headcount_indicators):
                logger.warning("Rejecting ungrounded company size '%s' (no headcount indicators in crawled text)", qual.estimated_company_size)
                qual.estimated_company_size = "Unknown"
                if "company_size" in qual.grounded_attributes:
                    qual.grounded_attributes["company_size"].status = "unknown"
                    qual.grounded_attributes["company_size"].value = "Unknown"
                    qual.grounded_attributes["company_size"].source_url = None
                if "estimated_company_size" not in qual.unknown_attributes:
                    qual.unknown_attributes.append("estimated_company_size")

        # Technology signals validation
        valid_tech = []
        for tech in qual.technology_signals:
            if tech.lower() in combined_text:
                valid_tech.append(tech)
            else:
                logger.warning("Rejecting ungrounded technology signal '%s'", tech)
        qual.technology_signals = valid_tech
        if not valid_tech and "technology_signals" not in qual.unknown_attributes:
            qual.unknown_attributes.append("technology_signals")

        # Products validation
        valid_products = []
        for prod in qual.products_or_services:
            clean_p = prod.strip().lower()
            if clean_p in combined_text:
                valid_products.append(prod)
                continue
            words = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', clean_p)]
            if not words:
                continue
            matching_words = [w for w in words if w in combined_text]
            if len(words) == 1:
                if words[0] in combined_text:
                    valid_products.append(prod)
                else:
                    logger.warning("Rejecting ungrounded product '%s'", prod)
            else:
                if len(matching_words) >= 2 and (len(matching_words) / len(words)) >= 0.7:
                    valid_products.append(prod)
                else:
                    logger.warning("Rejecting ungrounded product '%s'", prod)
        qual.products_or_services = valid_products
        if not valid_products and "products_or_services" not in qual.unknown_attributes:
            qual.unknown_attributes.append("products_or_services")

        # Geography validation
        if qual.geography != "Unknown" and qual.geography.lower() not in combined_text:
            logger.warning("Rejecting ungrounded geography '%s'", qual.geography)
            qual.geography = "Unknown"
            if "geography" in qual.grounded_attributes:
                qual.grounded_attributes["geography"].status = "unknown"
                qual.grounded_attributes["geography"].value = "Unknown"
                qual.grounded_attributes["geography"].source_url = None
            if "geography" not in qual.unknown_attributes:
                qual.unknown_attributes.append("geography")

        # Business model validation
        if qual.business_model.lower() not in ("unknown", "unknown / non-commercial"):
            if ("saas" in qual.business_model.lower() or "subscription" in qual.business_model.lower()) and \
               not ("saas" in combined_text or "subscription" in combined_text or "software as a service" in combined_text):
                logger.warning("Rejecting ungrounded SaaS business model '%s'", qual.business_model)
                qual.business_model = "Unknown"
                if "business_model" in qual.grounded_attributes:
                    qual.grounded_attributes["business_model"].status = "unknown"
                    qual.grounded_attributes["business_model"].value = "Unknown"
                    qual.grounded_attributes["business_model"].source_url = None
                if "business_model" not in qual.unknown_attributes:
                    qual.unknown_attributes.append("business_model")

        qual.unknown_attributes = sorted(list(set(qual.unknown_attributes)))
        return qual

    def _enforce_evidence_grounding(
        self, qual: CompanyQualification, pages: List[Dict[str, Any]]
    ) -> CompanyQualification:
        """
        Enforces strict evidence grounding on extracted company attributes.
        Prevents fabrication of employee counts, commercial offerings, business models,
        and technologies when crawled evidence is absent or indicates a demo/sandbox.
        """
        combined_text = " ".join([
            f"{p.get('title', '')} {p.get('content_markdown', '')} {str(p.get('metadata', {}))}"
            for p in pages
        ]).lower()

        is_sandbox_or_demo = any(
            marker in combined_text
            for marker in [
                "quotes to scrape",
                "quotes.toscrape",
                "demo sandbox",
                "educational demo",
                "sandbox for scraping",
                "for scraping",
            ]
        )

        unknowns = set(qual.unknown_attributes or [])

        if is_sandbox_or_demo:
            # 1. Commercial products: strictly empty for demo/sandbox
            qual.products_or_services = []
            unknowns.add("products_or_services")

            # 2. Company size / headcount: strictly Unknown
            qual.estimated_company_size = "Unknown"
            unknowns.add("estimated_company_size")

            # 3. Technologies: strictly empty unless explicitly mentioned in page body
            qual.technology_signals = []
            unknowns.add("technology_signals")

            # 4. Business model: Non-commercial
            qual.business_model = "Unknown / Non-Commercial"
            unknowns.add("business_model")

            # 5. Geography: Unknown
            qual.geography = "Unknown"
            unknowns.add("geography")

            # 6. Target audience: Unknown
            qual.target_audience = "Unknown"
            unknowns.add("target_audience")

            # 7. Value proposition: None / Unknown
            qual.value_proposition = "None / Unknown - Non-commercial educational demonstration sandbox."

        qual.unknown_attributes = sorted(list(unknowns))
        return qual

    def _select_content(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filters out empty bodies, removes duplicate page bodies by content hash,
        and orders pages by depth and business relevance.
        """
        seen_hashes = set()
        cleaned_pages = []

        for p in pages:
            markdown = (p.get("content_markdown") or "").strip()
            chash = p.get("content_hash") or ""

            # Skip empty bodies
            if len(markdown) < 5:
                continue

            # Deduplicate repeated templates/shells
            if chash and chash in seen_hashes:
                continue
            if chash:
                seen_hashes.add(chash)

            cleaned_pages.append(p)

        # Sort pages: depth 0 first, then order by depth ascending
        cleaned_pages.sort(key=lambda item: item.get("depth", 99))
        return cleaned_pages
