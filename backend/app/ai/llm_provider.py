import abc
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger("lead_intelligence.ai.provider")


@dataclass
class LLMExecutionResult:
    """Holds the raw JSON dictionary and execution metrics from an LLM invocation."""
    data: Dict[str, Any]
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    request_id: Optional[str] = None


class BaseLLMProvider(abc.ABC):
    """Abstract interface for LLM providers."""

    @abc.abstractmethod
    async def generate_qualification(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMExecutionResult:
        """Invokes the LLM and returns validated JSON output with token audit telemetry."""
        pass


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI API implementation using structured JSON outputs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY or ""
        self.model = model or settings.LLM_MODEL
        self.base_url = base_url or settings.LLM_BASE_URL or "https://api.openai.com/v1"

    async def generate_qualification(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMExecutionResult:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for live LLM qualification.")

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            if resp.status_code != 200:
                raise RuntimeError(
                    f"OpenAI API error (HTTP {resp.status_code}): {resp.text}"
                )

            res_json = resp.json()
            content_str = res_json["choices"][0]["message"]["content"]
            parsed_data = json.loads(content_str)
            usage = res_json.get("usage", {})

            return LLMExecutionResult(
                data=parsed_data,
                provider="openai",
                model=self.model,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=duration_ms,
                request_id=res_json.get("id"),
            )


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for zero-cost testing and development without live API keys.
    Generates intelligent, schema-compliant responses based on prompt keywords.
    """

    def __init__(self, model: str = "mock-gpt-4o-mini"):
        self.model = model

    async def generate_qualification(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMExecutionResult:
        start_time = time.perf_counter()

        # Simple heuristic to produce tailored mock data based on input domain/content
        prompt_lower = user_prompt.lower()
        is_quote_site = "quotes.toscrape" in prompt_lower
        is_demo_sandbox = (
            is_quote_site
            or "educational demo sandbox" in prompt_lower
            or "demo sandbox for scraping" in prompt_lower
            or "sandbox for scraping" in prompt_lower
            or "demo sandbox" in prompt_lower
        )

        if is_demo_sandbox:
            company_name = "Quotes to Scrape" if is_quote_site else "Demo Scraping Sandbox"
            industry = "Educational / Web Scraping Sandbox"
            summary = "An educational demonstration website hosting quotes and sample content for testing scraping algorithms."
            val_prop = "None / Unknown - Non-commercial educational demonstration sandbox."
            target_audience = "Unknown"
            products_or_services = []  # Strictly empty: no invented products
            business_model = "Unknown / Non-Commercial"
            geography = "Unknown"
            estimated_company_size = "Unknown"  # Strictly Unknown: no invented headcount
            technology_signals = []  # Strictly empty: no invented tech stack
            contact_signals = {}
            icp_score = 15  # Poor fit for B2B SaaS
            confidence = 0.95
            positives = ["Publicly accessible web domain", "Standard HTML markup structure"]
            negatives = [
                "No commercial B2B products or services identified",
                "No verifiable company headcount or organization structure",
                "Zero commercial operations, pricing, or sales model",
                "Educational demo sandbox not suited for enterprise software ICP",
            ]
            reasoning = "The crawled content demonstrates that the target is strictly an informational demonstration sandbox hosting quotes, not a commercial enterprise or software buyer. Commercial attributes including company size, products, technology stack, and business model are unevidenced in the crawled text and are designated as Unknown."
            source_root = "https://quotes.toscrape.com/" if is_quote_site else "https://example.com/"
            signals = [
                {
                    "signal": "Educational demo sandbox",
                    "evidence": "Website hosts quotes for demonstration purposes with no commercial products.",
                    "source_url": source_root,
                    "sentiment": "negative",
                    "status": "observed",
                    "confidence": 1.0,
                },
                {
                    "signal": "No commercial business model",
                    "evidence": "No pricing, SaaS subscriptions, or sales contacts found in crawled pages.",
                    "source_url": source_root,
                    "sentiment": "negative",
                    "status": "observed",
                    "confidence": 1.0,
                },
                {
                    "signal": "No commercial products or services",
                    "evidence": "Site contains no product catalog, software applications, or commercial offerings.",
                    "source_url": source_root,
                    "sentiment": "negative",
                    "status": "observed",
                    "confidence": 1.0,
                },
            ]
            observed_facts = [
                f"Target domain operates as an informational demonstration repository (URL: {source_root})",
                "No commercial product catalog, pricing, or checkout features exist on any crawled page",
            ]
            inferred_signals = [
                "Non-commercial intent deduced from the presence of sample quotations and complete absence of commercial licensing (confidence: 0.95)"
            ]
            unknown_attributes = [
                "estimated_company_size",
                "products_or_services",
                "business_model",
                "geography",
                "technology_signals",
            ]
            grounded_attributes = {
                "company_size": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No employee count, headcount, or team size stated in crawled content",
                    "source_url": None,
                },
                "business_model": {
                    "value": "Unknown / Non-Commercial",
                    "status": "inferred",
                    "confidence": 0.95,
                    "evidence": "Absence of commercial plans or checkout indicates non-commercial entity",
                    "source_url": source_root,
                },
                "products_or_services": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No commercial products, software platforms, or services offered",
                    "source_url": None,
                },
                "geography": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No corporate address, city, or regional operations specified",
                    "source_url": None,
                },
                "technology_signals": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No technology framework explicitly stated in body content",
                    "source_url": None,
                },
            }
        else:
            company_name = "Enterprise Tech Candidate"
            industry = "B2B SaaS & Supply Chain Intelligence"
            summary = "Cloud-native platform delivering automated workflows and business intelligence to mid-market and enterprise operators."
            val_prop = "Accelerating operational speed and predictive forecasting through autonomous workflows."
            target_audience = "Mid-market and enterprise procurement and technology leadership"
            products_or_services = ["Workflow Intelligence Platform", "API Data Integrations"]
            business_model = "B2B SaaS Subscription"
            geography = "North America"
            estimated_company_size = "51-200"
            technology_signals = ["REST API", "Cloud Native"]
            contact_signals = {"emails": ["contact@domain.com"], "phones": ["+1-800-555-0199"]}
            icp_score = 88  # Strong fit
            confidence = 0.92
            positives = [
                "Direct B2B workflow software platform",
                "Operates in target technology and supply chain sector",
                "Matches target geography and organization profile",
            ]
            negatives = ["Pricing tiers require direct sales contact"]
            reasoning = "Matches core ICP criteria: commercial enterprise software provider with verifiable B2B market offerings."
            signals = [
                {
                    "signal": "B2B SaaS offering",
                    "evidence": "Platform delivers enterprise-grade workflow automation.",
                    "source_url": "https://example.com/products",
                    "sentiment": "positive",
                    "status": "observed",
                    "confidence": 0.95,
                },
                {
                    "signal": "Clear value proposition",
                    "evidence": "Accelerates forecasting and reduces disruption latency.",
                    "source_url": "https://example.com/about",
                    "sentiment": "positive",
                    "status": "observed",
                    "confidence": 0.90,
                },
            ]
            observed_facts = [
                "Platform delivers enterprise-grade workflow automation (URL: https://example.com/products)"
            ]
            inferred_signals = [
                "Enterprise market focus inferred from platform integrations and procurement features (confidence: 0.90)"
            ]
            unknown_attributes = ["exact_revenue", "founding_date"]
            grounded_attributes = {
                "company_size": {
                    "value": "51-200",
                    "status": "observed",
                    "confidence": 0.85,
                    "evidence": "About page states 50-200 team members",
                    "source_url": "https://example.com/about",
                },
                "business_model": {
                    "value": "B2B SaaS Subscription",
                    "status": "observed",
                    "confidence": 0.95,
                    "evidence": "Products page outlines subscription software plans",
                    "source_url": "https://example.com/products",
                },
                "products_or_services": {
                    "value": "Workflow Intelligence Platform",
                    "status": "observed",
                    "confidence": 0.95,
                    "evidence": "Product features detailed on solutions page",
                    "source_url": "https://example.com/products",
                },
                "geography": {
                    "value": "North America",
                    "status": "observed",
                    "confidence": 0.90,
                    "evidence": "Offices listed in New York and San Francisco",
                    "source_url": "https://example.com/contact",
                },
                "technology_signals": {
                    "value": "REST API",
                    "status": "observed",
                    "confidence": 0.90,
                    "evidence": "Developer docs list REST API endpoints",
                    "source_url": "https://example.com/docs",
                },
            }

        mock_data = {
            "company_name": company_name,
            "company_summary": summary,
            "value_proposition": val_prop,
            "industry": industry,
            "target_audience": target_audience,
            "products_or_services": products_or_services,
            "business_model": business_model,
            "geography": geography,
            "estimated_company_size": estimated_company_size,
            "technology_signals": technology_signals,
            "contact_signals": contact_signals,
            "icp_score": icp_score,
            "confidence_score": confidence,
            "positive_signals": positives,
            "negative_signals": negatives,
            "qualification_reasoning": reasoning,
            "signals": signals,
            "observed_facts": observed_facts,
            "inferred_signals": inferred_signals,
            "unknown_attributes": unknown_attributes,
            "grounded_attributes": grounded_attributes,
        }

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return LLMExecutionResult(
            data=mock_data,
            provider="mock",
            model=self.model,
            input_tokens=len(user_prompt) // 4,
            output_tokens=320,
            total_tokens=(len(user_prompt) // 4) + 320,
            latency_ms=max(15.0, duration_ms),
            request_id="mock-req-001",
        )


def get_llm_provider() -> BaseLLMProvider:
    """Factory creating the configured LLM provider."""
    if settings.LLM_MOCK_MODE or not settings.LLM_API_KEY:
        logger.info("Using MockLLMProvider (LLM_MOCK_MODE=%s, has_api_key=%s)", settings.LLM_MOCK_MODE, bool(settings.LLM_API_KEY))
        return MockLLMProvider(model=settings.LLM_MODEL)

    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        return OpenAILLMProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
        )

    logger.warning("Unrecognized LLM_PROVIDER '%s'; falling back to MockLLMProvider", provider)
    return MockLLMProvider(model=settings.LLM_MODEL)
