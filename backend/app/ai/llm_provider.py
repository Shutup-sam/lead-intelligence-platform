import abc
import json
import logging
import re
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

        # Parse allowed crawled URLs and domain from prompt
        allowed_urls = re.findall(r"^- (https?://[^\s\n]+)", user_prompt, re.MULTILINE)
        if not allowed_urls:
            allowed_urls = re.findall(r"URL:\s*(https?://[^\s\n]+)", user_prompt)
        
        domain_match = re.search(r"Domain:\s*([^\s\n]+)", user_prompt)
        prompt_domain = domain_match.group(1).lower() if domain_match else "unknown.com"
        primary_url = allowed_urls[0] if allowed_urls else f"https://{prompt_domain}/"

        prompt_lower = user_prompt.lower()
        is_quote_site = "quotes.toscrape" in prompt_lower or "quotes.toscrape" in prompt_domain
        is_choice_india = "choiceindia.com" in prompt_lower or "choiceindia.com" in prompt_domain
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
            if "educational demo sandbox for scraping" in prompt_lower:
                sandbox_quote = "Educational demo sandbox for scraping."
            elif "quotes to scrape" in prompt_lower:
                sandbox_quote = "Quotes to Scrape"
            elif "demo sandbox" in prompt_lower:
                sandbox_quote = "demo sandbox"
            elif "sandbox" in prompt_lower:
                sandbox_quote = "sandbox"
            else:
                sandbox_quote = "scraping"

            source_root = primary_url
            signals = [
                {
                    "signal": "Educational demo sandbox",
                    "evidence": sandbox_quote,
                    "source_url": source_root,
                    "sentiment": "negative",
                    "status": "observed",
                    "confidence": 1.0,
                },
                {
                    "signal": "Non-commercial demonstration entity",
                    "evidence": sandbox_quote,
                    "source_url": source_root,
                    "sentiment": "negative",
                    "status": "observed",
                    "confidence": 1.0,
                },
            ]
            observed_facts = [
                f"Target domain operates as an informational demonstration repository (URL: {source_root})",
                f"Page content indicates non-commercial usage: '{sandbox_quote}'",
            ]
            inferred_signals = [
                "Non-commercial intent deduced from demonstration text and complete absence of commercial licensing (confidence: 0.95)"
            ]
            unknown_attributes = [
                "business_model",
                "estimated_company_size",
                "geography",
                "products_or_services",
                "target_audience",
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
                    "evidence": sandbox_quote,
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
        elif is_choice_india:
            company_name = "Choice"
            industry = "Financial Services / Stock Broking"
            summary = "Choice (formerly Choice Broking) is a full-service stock broker in India offering online trading in stocks, mutual funds, derivatives, and advisory."
            val_prop = "Full-service stock broking and wealth management platform offering online trading in stocks, commodities, currencies, and derivatives."
            target_audience = "Retail and institutional investors in India"
            products_or_services = ["Stock Trading", "Mutual Funds", "Commodities Trading", "IPOs", "Portfolio Management Services"]
            business_model = "Brokerage Commission / Financial Services"
            geography = "India"
            estimated_company_size = "Unknown"  # Headcount unstated in crawled pages
            technology_signals = []  # No tech framework stated in body content
            contact_signals = {"emails": ["care@choiceindia.com"], "phones": ["+91-88-2424-2424"]}
            icp_score = 20  # Disqualified: retail/institutional stock broking, not B2B SaaS
            confidence = 0.90
            positives = ["Active commercial business enterprise in India"]
            negatives = [
                "Stock broking firm rather than B2B software/SaaS vendor",
                "Consumer and retail investor financial services focus",
                "No verifiable company employee headcount in crawled content",
            ]
            reasoning = "Target operates as a full-service stock broking and wealth management financial services firm in India. It does not offer commercial B2B software products and does not match the target B2B SaaS ICP criteria."
            source_root = primary_url
            signals = [
                {
                    "signal": "Full-service stock broker in India",
                    "evidence": "Choice (formerly Choice Broking) is one of the best stock brokers in India. Start online trading in stocks, commodities, currencies, derivatives with India's leading full-service brokerage firm.",
                    "source_url": source_root,
                    "sentiment": "negative",
                    "status": "observed",
                    "confidence": 1.0,
                },
                {
                    "signal": "Retail and institutional brokerage offerings",
                    "evidence": "Start online trading in stocks, commodities, currencies, derivatives with India's leading full-service brokerage firm.",
                    "source_url": source_root,
                    "sentiment": "negative",
                    "status": "observed",
                    "confidence": 1.0,
                },
            ]
            observed_facts = [
                f"Choice operates as a full-service stock brokerage firm in India (URL: {source_root})",
                "Offers trading in stocks, commodities, mutual funds, IPOs, and bonds",
            ]
            inferred_signals = [
                "Retail consumer and financial services orientation deduced from trading accounts and retail trading app promotions (confidence: 0.90)"
            ]
            unknown_attributes = [
                "estimated_company_size",
                "technology_signals",
            ]
            grounded_attributes = {
                "company_size": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No employee count or team headcount stated in crawled content",
                    "source_url": None,
                },
                "business_model": {
                    "value": "Brokerage Commission / Financial Services",
                    "status": "observed",
                    "confidence": 0.95,
                    "evidence": "Start online trading in stocks, commodities, currencies, derivatives with India's leading full-service brokerage firm.",
                    "source_url": source_root,
                },
                "products_or_services": {
                    "value": "Stock Trading, Mutual Funds, IPOs, Bonds",
                    "status": "observed",
                    "confidence": 0.95,
                    "evidence": "Start online trading in stocks, commodities, currencies, derivatives with India's leading full-service brokerage firm.",
                    "source_url": source_root,
                },
                "geography": {
                    "value": "India",
                    "status": "observed",
                    "confidence": 1.0,
                    "evidence": "Choice (formerly Choice Broking) is one of the best stock brokers in India.",
                    "source_url": source_root,
                },
                "technology_signals": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No software framework or architecture explicitly named in body content",
                    "source_url": None,
                },
            }
        else:
            company_name = prompt_domain.split(".")[0].capitalize()
            industry = "Commercial Enterprise"
            summary = f"Commercial entity operating at {prompt_domain}."
            val_prop = "Commercial business offerings."
            target_audience = "Unknown"
            products_or_services = []
            business_model = "Unknown"
            geography = "Unknown"
            estimated_company_size = "Unknown"
            technology_signals = []
            contact_signals = {}
            icp_score = 40
            confidence = 0.60
            positives = ["Publicly accessible domain"]
            negatives = ["Unevidenced company metrics in crawled content"]
            reasoning = "Company attributes could not be fully substantiated from crawled text; metrics set to Unknown."
            source_root = primary_url
            signals = []
            observed_facts = [f"Domain active at {source_root}"]
            inferred_signals = []
            unknown_attributes = [
                "business_model",
                "estimated_company_size",
                "geography",
                "products_or_services",
                "technology_signals",
            ]
            grounded_attributes = {
                "company_size": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No employee count stated in crawled content",
                    "source_url": None,
                },
                "business_model": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No business model stated in crawled content",
                    "source_url": None,
                },
                "products_or_services": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No commercial products stated in crawled content",
                    "source_url": None,
                },
                "geography": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No geography stated in crawled content",
                    "source_url": None,
                },
                "technology_signals": {
                    "value": "Unknown",
                    "status": "unknown",
                    "confidence": 0.0,
                    "evidence": "No technologies stated in crawled content",
                    "source_url": None,
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
