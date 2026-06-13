"""Boot smoke test: the app factory builds and /healthz is registered. No stack required (constitution Art. V — CI never depends on the running stack)."""

from __future__ import annotations

from main import app, create_app


def test_app_factory_builds() -> None:
    built = create_app()
    assert built.title == "Raseed"


def test_healthz_route_registered() -> None:
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
    assert "/healthz" in paths
