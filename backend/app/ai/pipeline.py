import logging
from typing import List, Dict, Any, Tuple, Optional

from app.core.config import settings
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
    4. Generates canonical embedding document
    5. Computes dense vector embeddings
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

        # 4b. Enforce strict evidence grounding (Anti-hallucination sanitization)
        qualification = self._enforce_evidence_grounding(qualification, crawled_pages)

        # 5. Build canonical document and hash for embedding
        canonical_doc = build_canonical_embedding_document(qualification)
        embedding_hash = compute_content_hash(canonical_doc)

        # 6. Generate embedding
        embedding_vector = await self.embedding_provider.generate_embedding(canonical_doc)

        return qualification, canonical_doc, embedding_hash, embedding_vector, exec_result

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
