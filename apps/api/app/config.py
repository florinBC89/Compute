"""Runtime configuration (spec §55)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://computelayer:computelayer@localhost:5432/computelayer"
    redis_url: str | None = "redis://localhost:6379/0"
    object_storage_url: str | None = None

    #: Outputs at or above this size go to object storage instead of JSONB (§38).
    large_output_threshold_bytes: int = 1_048_576

    #: Stampede lock lifetime (§37).
    lock_ttl_seconds: int = 60

    #: Bootstrap workspace/project created on first start, for local dev.
    bootstrap_workspace: str = "local"
    bootstrap_project: str = "research-agent"
    bootstrap_api_key: str | None = None

    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    #: Human workspace (V0.2 slice): Supabase is used strictly as the
    #: end-user identity provider -- app data stays in this same Postgres.
    #: JWTs are verified against Supabase's JWKS endpoint (asymmetric keys),
    #: not a shared secret -- Supabase's own guidance recommends against the
    #: legacy HS256 shared-secret approach.
    supabase_url: str | None = None

    #: Platform-owned provider keys for the real research pipeline (§ human
    #: workspace). Users never supply their own -- spend is bounded per job
    #: by `default_job_cost_cap_usd` instead.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    tavily_api_key: str | None = None
    default_job_cost_cap_usd: float = 0.50

    #: Where app.worker's ComputeLayer client sends its compute.run() calls
    #: -- this process's own API, over the same HTTP protocol any external
    #: SDK user goes through (see app.agent.pipeline). In docker-compose
    #: that's the sibling `api` service; in production, the API's internal
    #: URL.
    internal_api_url: str = "http://localhost:8000/v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
