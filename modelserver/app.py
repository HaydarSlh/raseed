"""Model-server app (Phase 2 — replaces the Phase 0 stub).

Lifespan:
  1. Resolve artifact via get_current_artifact() seam.
  2. Compute SHA-256 of categorizer.onnx.
  3. Refuse to boot (SystemExit / startup failure) on missing artifact or mismatch.
  4. Load Categorizer; mark model as ready.
  5. /healthz reports ready only while model is loaded and verified.
"""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from modelserver.categorizer import Categorizer, get_current_artifact
from modelserver.config import settings
from modelserver.logging import RequestIDMiddleware, configure_logging
from modelserver.schemas import PredictRequest, PredictResponse

configure_logging()
log = structlog.get_logger()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Boot sequence: resolve artifact via seam → verify SHA → refuse-to-boot on failure."""
    artifact_ref = get_current_artifact(settings.artifact_dir)

    if not artifact_ref.onnx_path.exists():
        log.error("refuse_to_boot", reason="artifact_missing", path=str(artifact_ref.onnx_path))
        raise RuntimeError(
            f"Artifact not found at {artifact_ref.onnx_path} — refusing to boot."
        )

    computed = _sha256(artifact_ref.onnx_path)
    expected = settings.expected_sha256

    if expected != "unset" and computed != expected:
        log.error(
            "refuse_to_boot",
            reason="sha256_mismatch",
            expected=expected,
            computed=computed,
        )
        raise RuntimeError(
            f"SHA-256 mismatch for {artifact_ref.onnx_path} — refusing to boot. "
            f"Expected {expected!r}, got {computed!r}."
        )

    log.info("artifact_verified", sha256=computed)

    try:
        categorizer = Categorizer(
            artifact_ref=artifact_ref,
            taxonomy_path=settings.taxonomy_path,
            thresholds_path=settings.thresholds_path,
            max_sequence_length=settings.max_sequence_length,
        )
    except Exception as exc:
        log.error("refuse_to_boot", reason="load_failed", error=str(exc))
        raise RuntimeError(f"Failed to load model — refusing to boot: {exc}") from exc

    app.state.categorizer = categorizer
    app.state.model_sha256 = computed
    app.state.model_ready = True
    log.info("model_server_ready")

    yield

    app.state.model_ready = False
    log.info("model_server_shutdown")


app = FastAPI(
    title="Raseed Model Server",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)


# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/healthz", response_model=None)
async def healthz() -> dict | JSONResponse:
    """Ready only while a verified model is loaded (supersedes Phase 0 contract)."""
    ready = getattr(app.state, "model_ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "no verified model loaded"},
        )
    return {
        "status": "ok",
        "model": "loaded",
        "sha256": app.state.model_sha256,
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(body: PredictRequest) -> PredictResponse:
    """Classify a transaction description. Stateless; no persistence."""
    return app.state.categorizer.predict(
        description=body.description,
        top_k=body.top_k,
    )
