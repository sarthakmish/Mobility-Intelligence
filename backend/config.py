"""
============================================================
CONFIGURATION — All settings loaded from environment variables
============================================================
This file centralises every configurable parameter.
Change behaviour by editing .env — never hardcode secrets.
============================================================
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    All configuration is loaded from environment variables.
    Pydantic validates types automatically — if POSTGRES_PORT
    is set to "abc" in .env, it will raise an error at startup.
    """

    # ── Database ──────────────────────────────────────
    postgres_user: str = "postgres"
    postgres_password: str = ""  # Set POSTGRES_PASSWORD in environment
    postgres_db: str = "mobility_intelligence"
    postgres_host: str = "localhost"     # localhost for dev, Docker service name in prod
    postgres_port: int = 5432
    database_url: str = ""               # Built dynamically if not set

    # ── Redis ─────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── LLM Farm — single key, single domain for all models ──
    # All Claude, GPT, and embedding calls go through this proxy.
    llm_farm_api_key: str = ""
    llm_farm_base_url: str = "https://aoai-farm.bosch-temp.com"

    # ── LLM Farm deployment / model names ────────────
    # Claude models are identified by the URL segment used in rawPredict calls.
    # GPT / embedding are identified by the Azure deployment name.
    llm_farm_gpt_deployment: str = "gpt-5-mini-2025-08-07"
    llm_farm_embedding_deployment: str = (
        "askbosch-prod-farm-openai-text-embedding-3-small"
    )

    # ── Model Selection (from our cost analysis) ─────
    # CRITICAL tasks: CEO/CFO-facing analysis
    primary_model: str = "claude-sonnet-4-6"
    # HIGH tasks: structured scoring, validation
    validator_model: str = "claude-haiku-4-5"
    # Tier-1 fallback: same quality as primary, different rate-limit bucket
    primary_fallback_model: str = "claude-sonnet-4-5"
    # Tier-2 fallback: used if both Sonnet models are rate-limited
    primary_fallback_model_2: str = "claude-haiku-4-5"
    # ── Additional Validator Models ─────────────────────────────────────────
    # GPT-5.4: LLM Farm (same key, Bearer auth)
    gpt54_deployment: str = "gpt-5.4-2026-03-05"
    # Gemini 2.5 Pro: LLM Farm (same key, but subscription-key header)
    gemini_deployment: str = "google-gemini-2-5-pro"
    # Grok 4: separate Azure AI endpoint with api-key auth
    grok_base_url: str = "https://rbinbdo-vismai-mbr-resource.cognitiveservices.azure.com"
    grok_deployment: str = "grok-4-fast-reasoning"
    grok_api_key: str = ""  # Set GROK_API_KEY in environment
    # VOLUME tasks: news sentiment (batch)
    volume_model: str = "gpt-5-mini"
    # Embedding model for RAG
    embedding_model: str = "text-embedding-3-small"

    # ── SerpAPI ───────────────────────────────────────────
    serpapi_key: str = ""                # Free tier: 250 searches/month

    # ── Refresh Schedule ──────────────────────────────
    auto_refresh_hours: int = 24         # Auto-refresh interval (24h — industry news cycles daily)

    # ── API ───────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176,http://localhost:8080,http://10.210.86.157:5173,http://10.210.86.157:5174,http://10.210.86.157:3000,http://10.181.156.192:5173,http://10.181.156.192:5174,http://10.181.156.192:3000,http://10.181.156.192:8000,http://10.181.248.224:5173,http://10.181.248.224:5174,http://10.181.248.224:3000,http://192.168.1.10:5173,http://192.168.1.10:5174,http://192.168.1.10:3000"
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    # ── Cache TTL (seconds) ──────────────────────────
    analysis_cache_ttl: int = 86400      # 24 hours (analyses are stable; refresh clears stale ones)
    pestel_cache_ttl: int = 86400        # 24 hours
    tech_cache_ttl: int = 86400          # 24 hours

    # ── Currency ──────────────────────────────────────
    eur_usd_rate: float = 0.92

    @property
    def db_url(self) -> str:
        """Build database URL from individual components if not set directly."""
        if self.database_url:
            # Railway injects postgresql:// but asyncpg needs postgresql+asyncpg://
            url = self.database_url
            if url.startswith("postgresql://") or url.startswith("postgres://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        # Look for .env in backend/ (Docker) and ../ (local dev from backend/)
        env_file = (".env", "../.env")
        env_file_encoding = "utf-8"
        extra = "ignore"  # ignore unknown env vars (e.g. old GPT52_DEPLOYMENT)


# ── Singleton instance — import this everywhere ──
settings = Settings()
