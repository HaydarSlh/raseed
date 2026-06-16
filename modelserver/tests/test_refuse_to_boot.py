"""T011 — Refuse-to-boot tests (US1).

Missing artifact and SHA-256 mismatch must each cause the server to fail startup
(RuntimeError during lifespan). /healthz must never report ready without a
verified model. Refs: model-artifact.md, FR-013, SC-004.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient


def _patched_client(
    fixture_artifact_dir: Path,
    expected_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
    artifact_dir_override: Path | None = None,
    sha_override: str | None = None,
) -> TestClient:
    """Build a TestClient with optional overrides for artifact dir / SHA."""
    art_dir = artifact_dir_override or fixture_artifact_dir
    sha = sha_override or expected_sha256

    monkeypatch.setenv("MODELSERVER_ARTIFACT_DIR", str(art_dir))
    monkeypatch.setenv("MODELSERVER_EXPECTED_SHA256", sha)
    monkeypatch.setenv(
        "MODELSERVER_TAXONOMY_PATH", str(fixture_artifact_dir / "taxonomy.yaml")
    )
    monkeypatch.setenv(
        "MODELSERVER_THRESHOLDS_PATH", str(fixture_artifact_dir / "eval_thresholds.yaml")
    )

    from modelserver.config import Settings

    settings = Settings()

    import modelserver.app as app_module

    monkeypatch.setattr(app_module, "settings", settings)
    return TestClient(app_module.app, raise_server_exceptions=True)


def test_missing_artifact_refuses_to_boot(
    fixture_artifact_dir: Path,
    fixture_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty artifact dir → RuntimeError on startup (SC-004)."""
    # tmp_path has no categorizer.onnx
    client = _patched_client(
        fixture_artifact_dir, fixture_sha256, monkeypatch, artifact_dir_override=tmp_path
    )
    with pytest.raises(RuntimeError, match="refusing to boot"):
        with client:
            pass


def test_sha256_mismatch_refuses_to_boot(
    fixture_artifact_dir: Path,
    fixture_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid artifact file but wrong pinned SHA → RuntimeError on startup."""
    wrong_sha = "a" * 64  # definitely not the real SHA
    client = _patched_client(
        fixture_artifact_dir, fixture_sha256, monkeypatch, sha_override=wrong_sha
    )
    with pytest.raises(RuntimeError, match="refusing to boot"):
        with client:
            pass


def test_healthz_not_ready_without_model(
    fixture_artifact_dir: Path,
    fixture_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """/healthz should never report ok when the artifact is missing."""
    # We can't start the server without the artifact, so just verify the
    # error path fires (no sneaky 200 from a partially-started app).
    client = _patched_client(
        fixture_artifact_dir, fixture_sha256, monkeypatch, artifact_dir_override=tmp_path
    )
    with pytest.raises(RuntimeError):
        with client:
            resp = client.get("/healthz")
            assert resp.status_code != 200, (
                "/healthz reported ready without a verified model — refuse-to-boot failed"
            )
