"""Single typed settings source for the backend; required values fail fast at startup (constitution Art. I)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration. `extra='forbid'` rejects unknown keys; required fields
    have no default and so fail at startup when absent. Secrets resolve from Vault
    in real deployments; the env-file path is the documented trim rung (Art. V)."""

    model_config = SettingsConfigDict(extra="forbid", env_file=".env")

    app_env: str = "local"
    log_level: str = "INFO"

    # Data stores (services address each other by name, never localhost)
    database_url: str = "postgresql+asyncpg://raseed:raseed_local_dev@postgres:5432/raseed"
    redis_url: str = "redis://redis:6379/0"

    # MinIO holds model artifacts ONLY — never user data (Art. II)
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "raseed"
    minio_root_password: str = "raseed_local_dev"
    minio_artifacts_bucket: str = "model-artifacts"

    # Vault is the secret source of truth
    vault_addr: str = "http://vault:8200"
    vault_token: str = "raseed_local_dev_token"
    vault_secret_path: str = "secret/data/raseed"

    # JWT signing secret — resolved from Vault in non-local envs (Art. V)
    jwt_secret: str = "local-dev-jwt-secret-change-in-prod"
    jwt_lifetime_seconds: int = 3600

    # Lean model server
    modelserver_url: str = "http://modelserver:8080"

    # LLM adapter: Gemini -> Grok failover (Art. V); blank => FakeLLM in tests/local
    gemini_api_key: str = ""
    grok_api_key: str = ""
    use_fake_llm: bool = False

    # Phase 4 — agent + RAG tunables (embedder reuses gemini_api_key — see DECISIONS.md)
    embedding_model: str = "models/text-embedding-004"
    embedding_dim: int = 768
    agent_max_iterations: int = 8
    agent_token_budget: int = 16000
    session_ttl_seconds: int = 1800
    write_rate_per_min: int = 10


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — deterministic in-process work uses lru_cache (Art. V)."""
    return Settings()
