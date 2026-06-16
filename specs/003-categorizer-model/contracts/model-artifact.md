# Contract: model artifact, model card & refuse-to-boot (Phase 2)

Activates the SHA-256 guard the Phase 0 stub deliberately left off
(`specs/001-repo-skeleton/contracts/modelserver-healthz.md` → superseded here).

## Artifact bundle (`modelserver/artifacts/`, Git LFS)
- `categorizer.onnx` — served model graph (neural champion with embedded temperature
  scalar, or TF-IDF+LR pipeline via skl2onnx).
- `tokenizer.json` — WordPiece tokenizer (neural champion only).
- `model_card.md` — provenance record.

## Model card required fields *(FR-018, FR-019)*
- `data_hash` — holdout content hash (== `split_manifest.hashes.holdout`).
- `metrics` — champion macro-F1 + per-class F1 + latency + cost, plus the classical
  baseline and Gemini zero-shot numbers (the three-way record).
- `freeze_policy` — **MUST state**: full fine-tune for the foundation model; partial
  unfreeze for in-stack retrains (Phase 5).
- `artifact_sha256` — pinned SHA-256 of `categorizer.onnx`.
- `taxonomy_version`, `calibration_method`, `seeds`.

## Refuse-to-boot behavior *(FR-013, Art. III)*
1. On startup the server computes SHA-256 of `categorizer.onnx` and compares it to
   the **expected hash pinned in typed settings** (sourced from the model card).
2. **Missing artifact** → the server fails to become ready / exits non-zero. It
   MUST NOT serve.
3. **Hash mismatch** → same: fail to become ready / exit non-zero. No warn-and-serve,
   no lazy verification on first request.
4. Only after a successful match does `/predict` accept traffic and `/healthz` report
   ready (predict-api.md).
5. The guard fires **100% of the time** on missing/mismatched artifacts. *(SC-004)*

## Leanness *(FR-014, Art. III)*
The serving image MUST NOT contain `torch` or `transformers` (nor `scikit-learn` at
serve time). Allowed runtime deps: `fastapi`, `uvicorn`, `onnxruntime`, `numpy`,
`tokenizers`, `structlog`, `pydantic[-settings]`. Verified by image inspection.
*(SC-007)*

## Source of the served artifact *(FR-016 + research R7)*
This phase mounts the pinned artifact from the image (committed via LFS). MinIO-
sourced loading and hot reload are **deferred to Phase 5** (runtime artifact
rotation); `minio.py` stays a stub. MinIO remains "model artifacts only".

**"Get current artifact" seam (forward-compat constraint, FR-016)**: the model-server
MUST resolve its artifact bytes + path through a single thin provider (e.g.
`get_current_artifact() -> ArtifactRef`). Boot, SHA-256 verification, and load logic
depend only on that seam — never on a concrete source. Phase 2 implements a mounted-
file provider; Phase 5 swaps in a MinIO-by-SHA provider **without touching boot or
hash-verification code**.
