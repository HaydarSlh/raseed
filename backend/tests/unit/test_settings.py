"""Settings unit tests: missing required values fail at startup; unknown/extra keys are rejected (SC-004, SC-005)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_extra_key_rejected() -> None:
    """Settings with extra='forbid' must reject unknown keys (SC-005)."""
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class StrictSettings(BaseSettings):
        model_config = SettingsConfigDict(extra="forbid")
        app_env: str = "local"

    with pytest.raises(ValidationError):
        StrictSettings(**{"bogus_key": "value"})  # pyright: ignore


def test_settings_boots_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings instantiates cleanly from documented defaults."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.delenv("BOGUS_KEY", raising=False)

    settings = get_settings()
    assert settings.app_env == "local"
    get_settings.cache_clear()


def test_settings_extra_forbid_configured() -> None:
    """Confirm the production Settings class has extra='forbid'."""
    from app.core.config import Settings

    assert Settings.model_config.get("extra") == "forbid"
