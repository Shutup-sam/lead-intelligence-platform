import abc
import hashlib
import logging
import math
import random
from typing import List, Optional
import httpx

from app.core.config import settings
from app.ai.models import CompanyQualification

logger = logging.getLogger("lead_intelligence.ai.embeddings")


def build_canonical_embedding_document(qualification: CompanyQualification) -> str:
    """
    Constructs a deterministic canonical text document representing the business entity
    for dense vector embedding and semantic lookalike search.
    """
    products_str = ", ".join(qualification.products_or_services) if qualification.products_or_services else "None listed"
    tech_str = ", ".join(qualification.technology_signals) if qualification.technology_signals else "None listed"
    positives_str = "; ".join(qualification.positive_signals) if qualification.positive_signals else "None"

    return f"""Company:
{qualification.company_name}

Industry:
{qualification.industry}

Summary:
{qualification.company_summary}

Value proposition:
{qualification.value_proposition}

Products & Services:
{products_str}

Target audience:
{qualification.target_audience}

Business Model:
{qualification.business_model}

Geography:
{qualification.geography}

Technology:
{tech_str}

ICP Signals:
{positives_str}
""".strip()


def compute_content_hash(text: str) -> str:
    """Generates a SHA-256 digest of the canonical document for embedding idempotency."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BaseEmbeddingProvider(abc.ABC):
    """Abstract interface for dense vector embedding generation."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        pass

    @abc.abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        pass


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI API implementation using text-embedding-3-small (1536 dims)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        dimension: int = 1536,
    ):
        self.api_key = api_key or settings.LLM_API_KEY or ""
        self.model = model or settings.EMBEDDING_MODEL
        self.base_url = base_url or settings.LLM_BASE_URL or "https://api.openai.com/v1"
        self._dimension = dimension or settings.EMBEDDING_DIMENSION

    @property
    def dimension(self) -> int:
        return self._dimension

    async def generate_embedding(self, text: str) -> List[float]:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for live embedding generation.")

        url = f"{self.base_url.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": text,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"OpenAI Embeddings API error (HTTP {resp.status_code}): {resp.text}"
                )

            data = resp.json()
            embedding = data["data"][0]["embedding"]
            return embedding


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic mock provider producing unit-length 1536-dimensional vectors.
    Uses the SHA-256 hash of the content as a pseudo-random seed, guaranteeing
    that identical content yields identical vectors without external API calls.
    """

    def __init__(self, dimension: int = 1536):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def generate_embedding(self, text: str) -> List[float]:
        # Seed random generator with integer from content hash
        seed_int = int(compute_content_hash(text)[:16], 16)
        rng = random.Random(seed_int)

        # Generate random values
        raw_vector = [rng.uniform(-1.0, 1.0) for _ in range(self._dimension)]

        # Normalize to unit length (L2 norm = 1.0) for cosine similarity
        norm = math.sqrt(sum(x * x for x in raw_vector))
        return [round(x / norm, 6) for x in raw_vector]


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory creating the configured embedding provider."""
    if settings.EMBEDDING_MOCK_MODE or not settings.LLM_API_KEY:
        logger.info(
            "Using MockEmbeddingProvider (EMBEDDING_MOCK_MODE=%s, has_api_key=%s)",
            settings.EMBEDDING_MOCK_MODE, bool(settings.LLM_API_KEY)
        )
        return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)

    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.EMBEDDING_MODEL,
            base_url=settings.LLM_BASE_URL,
            dimension=settings.EMBEDDING_DIMENSION,
        )

    logger.warning("Unrecognized EMBEDDING_PROVIDER '%s'; falling back to MockEmbeddingProvider", provider)
    return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
