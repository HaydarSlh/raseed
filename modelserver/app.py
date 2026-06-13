"""Lean model-server (onnxruntime + numpy, NO torch). Phase 0 serves /healthz reporting "no model loaded" with no refuse-to-boot guard (guard arrives in Phase 2, constitution Art. III)."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Raseed Model Server", version="0.0.0")

# Phase 0: no artifact is present and NO SHA-256/refuse-to-boot guard is enforced.
# Phase 2 loads the pinned ONNX model and activates the hash guard here.
_MODEL_LOADED = False


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Always healthy without a model; reports "no model loaded" (contract:
    specs/001-repo-skeleton/contracts/modelserver-healthz.md)."""
    if _MODEL_LOADED:
        return {"status": "ok", "model": "loaded"}
    return {"status": "ok", "model": "none", "detail": "no model loaded"}
