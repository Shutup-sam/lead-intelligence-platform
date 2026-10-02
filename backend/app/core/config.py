from typing import List, Union, Optional
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    PROJECT_NAME: str = "AI Lead Intelligence Platform"
    API_V1_PREFIX: str = "/api/v1"

    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "lead_intelligence"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lead_intelligence"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_async_db_url(cls, v: str) -> str:
        if isinstance(v, str):
            # Ensure using asyncpg driver for async SQLAlchemy
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"
    ARQ_QUEUE_NAME: str = "arq:queue"

    # Crawler Settings (Milestone 2)
    CRAWLER_REQUEST_TIMEOUT: int = 15
    CRAWLER_DELAY_SECONDS: float = 1.0
    CRAWLER_MAX_PAGES: int = 6
    CRAWLER_MAX_DEPTH: int = 2
    CRAWLER_MAX_RETRIES: int = 2
    CRAWLER_USER_AGENT: str = "LeadIntelligenceBot/1.0 (+https://leadintel.platform/bot)"

    # AI / LLM Qualification Settings (Milestone 3)
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MOCK_MODE: bool = True
    LLM_MAX_INPUT_CHARS: int = 16000
    LLM_MAX_OUTPUT_TOKENS: int = 2000

    # Embeddings / pgvector Settings (Milestone 3)
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_MOCK_MODE: bool = True

    # Multi-tenant Auth & Security (Milestone 6)
    JWT_SECRET_KEY: str = "lead-intel-super-secure-jwt-key-for-saas-platform"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Organization Usage Limits (Milestone 6)
    MAX_ACTIVE_JOBS_PER_ORG: int = 5
    MAX_MONTHLY_CRAWLS_PER_ORG: int = 100
    MAX_MONTHLY_PAGES_PER_ORG: int = 1000
    MAX_MONTHLY_AI_QUALIFICATIONS_PER_ORG: int = 500

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        import json
        try:
            return json.loads(v)
        except Exception:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]


settings = Settings()
