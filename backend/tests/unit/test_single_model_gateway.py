"""Guard: no hosted-model SDK calls outside app/infra/llm.py; domain errors map to structured HTTP (SC-007, FR-012, FR-013)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_no_direct_model_sdk_calls_outside_adapter() -> None:
    """Grep the codebase for any direct Gemini/Grok SDK imports outside infra/llm.py."""
    app_dir = Path(__file__).parent.parent.parent / "app"
    patterns = [
        r"google\.genai",
        r"google\.generativeai",
        r"import genai",
        r"from genai",
        r"x\.ai",
        r"api\.x\.ai",
    ]
    violations: list[str] = []
    for py_file in app_dir.rglob("*.py"):
        if py_file.parent.name == "infra" and py_file.name in ("llm.py", "embeddings.py"):
            continue  # infra adapters are allowed to use model SDKs
        text = py_file.read_text(encoding="utf-8")
        for pattern in patterns:
            import re
            if re.search(pattern, text):
                violations.append(f"{py_file}: matched {pattern!r}")

    assert not violations, "Direct model SDK calls found outside infra/llm.py:\n" + "\n".join(violations)


def test_raseed_error_maps_to_structured_http() -> None:
    """RaseedError subclasses produce structured JSON responses, never stack traces."""
    import os
    os.environ.setdefault("JWT_SECRET", "test-secret")
    os.environ.setdefault("APP_ENV", "local")

    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.core.exceptions import NotFoundError
    from main import create_app

    app = create_app()

    @app.get("/test-error")
    async def _raise():
        raise NotFoundError("item missing")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/test-error")
    assert r.status_code == 404
    body = r.json()
    assert "detail" in body
    assert "traceback" not in r.text.lower()
    assert "item missing" in body["detail"]
    get_settings.cache_clear()
