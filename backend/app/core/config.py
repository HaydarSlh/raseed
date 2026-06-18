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
    # gemini-embedding-001 supports configurable output dims (Matryoshka); we request
    # embedding_dim to match the pgvector column. text-embedding-004 is retired.
    embedding_model: str = "models/gemini-embedding-001"
    embedding_dim: int = 768
    agent_max_iterations: int = 8
    agent_token_budget: int = 16000
    session_ttl_seconds: int = 1800
    write_rate_per_min: int = 10

    # Phase 5 — ML lifecycle & ops tunables (all seeded; see DECISIONS.md for rationale)
    retrain_threshold_prod: int = 100
    retrain_threshold_demo: int = 10
    retrain_cooldown_days: int = 14
    demo_mode: bool = False
    slack_webhook_url: str = ""  # resolved from Vault in non-local envs (T002)

    # Drift thresholds — seeded from Phase-2 holdout confidence distribution (DECISIONS.md)
    # Required to have defaults: extra='forbid' makes fields without defaults mandatory env vars
    drift_mean_confidence_min: float = 0.70
    drift_correction_rate_max: float = 0.20
    drift_psi_max: float = 0.20
    drift_new_merchant_rate_max: float = 0.15


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — deterministic in-process work uses lru_cache (Art. V)."""
    return Settings()
