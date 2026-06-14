"""Vault adapter: resolves required secrets at startup; refuses to boot if any required secret is missing in non-local environments (constitution Art. V, FR-010, SC-004)."""

from __future__ import annotations

import hvac
import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)

# Secrets this app requires; the Vault key name maps to the settings field name.
_REQUIRED_SECRETS: dict[str, str] = {
    "jwt_secret": "jwt_secret",
}


def load_secrets_into_settings() -> dict[str, str]:
    """Connect to Vault and return the resolved secrets dict.

    In APP_ENV=local the Vault call is attempted but failure is tolerated
    (the .env defaults are the documented local fallback). In any other
    environment a missing secret raises immediately — refuse to boot.
    """
    settings = get_settings()
    is_local = settings.app_env.lower() == "local"

    resolved: dict[str, str] = {}
    try:
        client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
        if not client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

        secret = client.secrets.kv.v2.read_secret_version(
            path=settings.vault_secret_path.removeprefix("secret/data/"),
            mount_point="secret",
        )
        data: dict[str, str] = secret["data"]["data"]

        for field, vault_key in _REQUIRED_SECRETS.items():
            value = data.get(vault_key)
            if value:
                resolved[field] = value
                log.info("vault.secret.loaded", field=field)
            elif not is_local:
                raise RuntimeError(
                    f"Required Vault secret '{vault_key}' is missing; refusing to boot."
                )
            else:
                log.warning("vault.secret.missing.local", field=field, fallback="using .env default")

    except Exception as exc:
        if is_local:
            log.warning("vault.unavailable.local", reason=str(exc), fallback="using .env defaults")
        else:
            log.error("vault.unavailable.fatal", reason=str(exc))
            raise RuntimeError(
                f"Vault unavailable in non-local environment — refusing to boot: {exc}"
            ) from exc

    return resolved
