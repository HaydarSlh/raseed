"""T012 — Input-validation tests (US1).

Empty / whitespace-only / oversized description, and out-of-range top_k → HTTP 422
structured error, never a 500 or a stack trace. Refs: FR-017, predict-api.md.
"""

from __future__ import annotations

from starlette.testclient import TestClient


def _assert_422(resp, label: str) -> None:
    assert resp.status_code == 422, f"{label}: expected 422, got {resp.status_code}"
    body = resp.json()
    # FastAPI's default 422 has a `detail` key — no raw stack trace.
    assert "detail" in body, f"{label}: missing 'detail' in response"
    assert "traceback" not in resp.text.lower(), f"{label}: stack trace leaked"


def test_empty_description_is_422(test_client: TestClient) -> None:
    _assert_422(test_client.post("/predict", json={"description": ""}), "empty string")


def test_whitespace_only_is_422(test_client: TestClient) -> None:
    _assert_422(
        test_client.post("/predict", json={"description": "   \t\n  "}),
        "whitespace-only",
    )


def test_oversized_description_is_422(test_client: TestClient) -> None:
    _assert_422(
        test_client.post("/predict", json={"description": "x" * 513}),
        "513 chars",
    )


def test_top_k_zero_is_422(test_client: TestClient) -> None:
    _assert_422(
        test_client.post("/predict", json={"description": "COFFEE", "top_k": 0}),
        "top_k=0",
    )


def test_top_k_six_is_422(test_client: TestClient) -> None:
    _assert_422(
        test_client.post("/predict", json={"description": "COFFEE", "top_k": 6}),
        "top_k=6",
    )


def test_missing_description_is_422(test_client: TestClient) -> None:
    _assert_422(test_client.post("/predict", json={"top_k": 3}), "missing description")


def test_valid_512_char_description_is_200(test_client: TestClient) -> None:
    resp = test_client.post("/predict", json={"description": "A" * 512})
    assert resp.status_code == 200, f"512-char description rejected: {resp.text}"
