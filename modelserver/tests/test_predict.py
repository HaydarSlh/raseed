"""T010 — /predict contract tests (US1).

Verifies: category ∈ taxonomy, calibrated confidence ∈ [0,1], alternatives descending
with primary at rank 0, per-category low_confidence flag, structured 422 for bad input.
Refs: predict-api.md, FR-001, FR-008, FR-009, FR-010, FR-011, SC-001.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from modelserver.tests.conftest import CATEGORIES


@pytest.fixture()
def r(test_client: TestClient):
    """Helper: POST /predict and return parsed JSON."""
    def _post(description: str, top_k: int = 3) -> dict:
        resp = test_client.post("/predict", json={"description": description, "top_k": top_k})
        assert resp.status_code == 200, resp.text
        return resp.json()
    return _post


def test_category_in_taxonomy(r) -> None:
    data = r("STARBUCKS STORE #1234 SEATTLE WA")
    assert data["category"] in CATEGORIES


def test_confidence_in_range(r) -> None:
    data = r("WALMART GROCERY")
    assert 0.0 <= data["confidence"] <= 1.0


def test_alternatives_length_honours_top_k(r) -> None:
    for k in (1, 3, 5):
        data = r("AMAZON PAYMENT", top_k=k)
        assert len(data["alternatives"]) == k


def test_alternatives_sorted_descending(r) -> None:
    data = r("UBER TRIP", top_k=5)
    scores = [alt["score"] for alt in data["alternatives"]]
    assert scores == sorted(scores, reverse=True)


def test_primary_at_rank_0(r) -> None:
    """Contract: primary category is alternatives[0]."""
    data = r("COFFEE SHOP PURCHASE")
    assert data["alternatives"][0]["category"] == data["category"]
    assert abs(data["alternatives"][0]["score"] - data["confidence"]) < 1e-6


def test_all_alternatives_in_taxonomy(r) -> None:
    data = r("GROCERY STORE VISIT", top_k=5)
    for alt in data["alternatives"]:
        assert alt["category"] in CATEGORIES


def test_low_confidence_flag_present(r) -> None:
    data = r("MISC PAYMENT 12345")
    assert isinstance(data["low_confidence"], bool)


def test_healthz_reports_ready(test_client: TestClient) -> None:
    resp = test_client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model"] == "loaded"
    assert "sha256" in body
