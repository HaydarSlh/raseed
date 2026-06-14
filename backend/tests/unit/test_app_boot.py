"""Boot smoke test: the app factory builds and /healthz is registered. No stack required (constitution Art. V — CI never depends on the running stack)."""

from __future__ import annotations

from main import app, create_app


def _collect_paths(routes: list) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        if hasattr(route, "path"):
            paths.add(route.path)
        # FastAPI 0.115+ wraps included routers in _IncludedRouter (no path attr)
        if hasattr(route, "original_router"):
            paths |= _collect_paths(route.original_router.routes)
        elif hasattr(route, "routes"):
            paths |= _collect_paths(route.routes)
    return paths


def test_app_factory_builds() -> None:
    built = create_app()
    assert built.title == "Raseed"


def test_healthz_route_registered() -> None:
    assert "/healthz" in _collect_paths(app.routes)
