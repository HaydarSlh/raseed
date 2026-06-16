"""Typed settings for the model-server. extra='forbid' catches env-var typos."""

from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MODELSERVER_",
        extra="forbid",
    )

    # Artifact location — the seam in categorizer.py resolves these paths.
    artifact_dir: Path = Path("modelserver/artifacts")
    # SHA-256 of categorizer.onnx, pinned after Colab champion export (T030).
    # Set to "fixture" in tests via MODELSERVER_EXPECTED_SHA256=fixture env var.
    expected_sha256: str = "3f5dc0e0edb4efd017fc515785f2daf2976314738ff14ef733f121c25f45b331"

    taxonomy_path: Path = Path("training/taxonomy.yaml")
    thresholds_path: Path = Path("eval_thresholds.yaml")

    host: str = "0.0.0.0"
    port: int = 8080

    # Inference
    max_sequence_length: int = 128
    predict_timeout_ms: int = 500

    @model_validator(mode="after")
    def _validate_sha(self) -> "Settings":
        if self.expected_sha256 == "unset":
            import warnings
            warnings.warn(
                "MODELSERVER_EXPECTED_SHA256 is not set — refuse-to-boot will fail "
                "unless a verified model exists at the artifact_dir.",
                stacklevel=2,
            )
        return self


settings = Settings()
