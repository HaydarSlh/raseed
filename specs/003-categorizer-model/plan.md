# Implementation Plan: Categorizer — Trained Offline, Served Lean

**Branch**: `003-categorizer-pipeline` (spec dir `003-categorizer-model`) | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-categorizer-model/spec.md`

## Summary

Phase 2 turns a transaction description into a category + calibrated confidence,
from a developer-fine-tuned model served behind the lean in-stack `modelserver`.
Three deliverable slices: (US1) the lean `/predict` service — category + calibrated
confidence + top-k alternatives + a per-category low-confidence flag, `/healthz`
ready only with a verified model, and **strict refuse-to-boot** on a missing
artifact or SHA-256 mismatch (the Phase 0 stub guard activates now); (US2) **CI
gate #1** — on the frozen holdout, the champion must beat the classical baseline by
a committed margin AND clear a ratcheting absolute macro-F1 floor, run entirely
from committed artifacts (Git LFS), never the running stack; (US3) reproducible
offline training & provenance — a coarse ~10–15 category locked taxonomy, a
fixed-seed stratified split with a frozen holdout, a three-way comparison
(TF-IDF+LR vs fine-tuned DistilBERT vs Gemini zero-shot) recorded in DECISIONS.md,
ONNX export, and a model card (data hash, metrics, freeze policy, pinned SHA-256).

Foundation fine-tuning runs **offline in Colab on GPU** (notebooks are the
deliverable; torch never enters a serving image). The reproducible classical
baseline trains on CPU and doubles as the gate's always-present comparison and as a
mechanism check for the whole harness while the developer produces the champion.
No new database tables: a prediction is returned, never persisted (persistence is
Phase 3). The served confidence is calibrated so the per-category 97%-precision
threshold rule is meaningful.

## Technical Context

**Language/Version**: Python 3.12 across `modelserver/` (serving) and `training/`
(offline). React frontend is untouched this phase.

**Primary Dependencies**:
- *Serving (`modelserver/`, must stay lean — Art. III)*: FastAPI, uvicorn,
  `onnxruntime`, `numpy`, and `tokenizers` (the Rust-backed WordPiece tokenizer —
  torch-free, a few MB) for DistilBERT-style input encoding. **No torch, no
  transformers, no scikit-learn at serve time.**
- *Offline training (`training/`, Colab GPU + a CPU-runnable classical path)*:
  `scikit-learn` (TF-IDF + logistic-regression baseline), `torch` + `transformers`
  + `datasets` (DistilBERT fine-tune, Colab only), `google-genai` via the backend
  LLM-adapter pattern (Gemini zero-shot baseline), `onnx` + `skl2onnx` /
  `optimum`/`onnxruntime` for export, `pandas`/`pyarrow` for the dataset + holdout.

**Storage**: No new Postgres tables and **no Alembic migration** this phase
(`transactions.provenance|confidence|needs_review` already exist from Phase 1 and
are written by Phase 3, not here). Artifacts (ONNX + tokenizer + holdout) are
committed via **Git LFS** as the source of record. The served artifact is pinned by
SHA-256 and mounted into the `modelserver` image; **MinIO-sourced loading + hot
reload is deferred to Phase 5** (DESIGN C), where runtime artifact rotation first
exists — there is nothing to rotate yet, so `minio.py` stays a stub. Loading goes
through a thin **"get current artifact" seam** (mounted-file provider now) so Phase 5
can swap to a MinIO-by-SHA provider without touching boot/hash-verification logic.

**Testing**: pytest for the model-server (`modelserver/tests/`): `/predict`
contract (category in taxonomy, confidence in [0,1], top-k, low-confidence flag),
input-validation errors, and refuse-to-boot (missing artifact / hash mismatch) via
a tiny fixture ONNX. A standalone, stack-independent **gate script** computes
macro-F1 for champion + baseline on the committed holdout and asserts the pass
rule; CI runs it as a new job. Offline-training notebooks/scripts are validated by
the deterministic-split test and the classical-baseline run; the champion's real
numbers come from the developer's Colab run.

**Target Platform**: Linux containers in the existing docker-compose stack;
`modelserver` reachable as `http://modelserver:8080` (never localhost). CI runs on
ubuntu-latest with Git LFS checkout, no compose.

**Project Type**: Web-application monorepo extension. Real code lands in the
existing `modelserver/` and `training/` trees plus a CI gate job; no new top-level
directories.

**Performance Goals**: `/predict` p95 < 200 ms per single prediction on CPU
(onnxruntime); short descriptions make DistilBERT-ONNX feasible at this bar.
Inference latency and cost-per-call are measured for all three approaches and
recorded (SC-001, SC-006).

**Constraints**: Serving image stays lean — **no torch/transformers** (Art. III).
Refuse-to-boot active on missing artifact or SHA-256 mismatch. Frozen holdout
touched only by the gate. CI never depends on the running stack — artifacts arrive
via LFS. Every prediction is a member of the locked taxonomy. Confidence is
calibrated. The Gemini zero-shot baseline's classification prompt lives in
`prompts/` (Art. IV), runs offline on the dataset only — never on user data.
DECISIONS.md records the three real numbers and both threshold rules.

**Scale/Scope**: Cleaned 18-category taxonomy (v2.0.0); one served model; one CI gate;
single-item prediction is the contract (batch is optional convenience). Dataset is
`laramee26openBankTransactionData.xlsx` (UK/GBP open banking; replaced the synthetic
Kaggle USA set on 2026-06-16 — see `docs/DECISIONS.md`); holdout is a fixed slice.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This phase **activates** ML Lifecycle Integrity (Art. III) — the refuse-to-boot
guard and CI gate #1 the earlier phases only scaffolded.

| Principle | Phase-2 obligation | Status |
|-----------|--------------------|--------|
| I. Layered, Async Architecture | `modelserver` is a self-contained lean FastAPI service: async `/predict`, typed settings (`extra='forbid'`) for artifact path + pinned SHA, domain-exception→structured-error mapping (no stack traces). The backend `modelserver_client` (stubbed) stays the only caller seam, awaited with timeout+retry — but wiring it into ingestion is Phase 3, not here. | PASS |
| II. Isolation & Data Protection (NON-NEGOTIABLE) | `/predict` is stateless inference over a description string — no `user_id`, no persistence, no raw files. The service is internal-only (compose network). Only the **zero-shot eval** crosses the LLM boundary, and only over the public Kaggle dataset offline — never user data. MinIO still holds artifacts only (untouched this phase). | PASS |
| III. ML Lifecycle Integrity | **Headline & activation.** Training labels are the dataset's ground-truth labels; the frozen holdout is touched only by the gate. Serving stays lean (onnxruntime + numpy + tokenizers, **no torch**). The trainer remains the single heavy image (foundation training is Colab GPU; the trainer's in-stack retrain is Phase 5). The artifact ships a model card + pinned SHA-256, and the server **refuses to boot on mismatch** — the guard goes live now. | PASS (activate) |
| IV. Bounded Agent & Grounded RAG | No agent/RAG. The Gemini zero-shot baseline uses a **file-based prompt in `prompts/`** (no inline strings) through the single adapter pattern, offline. | PASS (scoped) |
| V. Quality & Operations | CI gate #1 lives in `eval_thresholds.yaml` (categorizer block) and a regression blocks merge; artifacts reach CI via **Git LFS**, never the stack. structlog JSON + request IDs in the model-server; a span per prediction carrying latency. Inference calls bounded; the zero-shot eval uses the adapter's timeout/retry (4xx not retried). DECISIONS.md records the three-way numbers, the winner rule, the threshold rule, and the seeded macro-F1 floor. | PASS (activate gate #1) |

**Stack fidelity**: lean onnxruntime model-server (no torch), trainer as the single
heavy image (Colab for foundation), Git LFS for CI artifacts, Gemini via the
adapter, `eval_thresholds.yaml` gate — exactly the fixed stack, no substitutions.

**Result**: PASS. No violations; Complexity Tracking empty. Re-checked post-design.

### Post-Design Re-Check

After Phase 1 design (research, data-model, contracts, quickstart): the design adds
no torch to any serving image, keeps `/predict` stateless and internal, touches the
holdout only in the gate, runs the gate stack-independently from LFS artifacts,
keeps the zero-shot prompt in `prompts/`, and records every number in DECISIONS.md.
Serving from a pinned, mounted LFS artifact (MinIO deferred to Phase 5) is the
minimal surface that satisfies refuse-to-boot without inventing runtime artifact
rotation that does not yet exist. **Constitution Check still PASS.** Complexity
Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-categorizer-model/
├── plan.md              # This file
├── research.md          # Phase 0 — dataset/taxonomy, split, calibration, threshold rule, ONNX/tokenizer, artifact delivery, gate, Colab HIL
├── data-model.md        # Phase 1 — predict schema, taxonomy, eval_thresholds schema, model-card schema, split manifest (NO DB tables)
├── quickstart.md        # Phase 1 — serve/predict, refuse-to-boot, low-confidence, gate, reproducible split, lean-image checks
├── contracts/           # Phase 1 output
│   ├── predict-api.md        # POST /predict + /healthz (ready-only-with-model) contract
│   ├── model-artifact.md     # artifact + tokenizer + model card + pinned SHA-256 + refuse-to-boot
│   └── ci-gate.md            # gate #1: margin + ratcheting floor, LFS inputs, stack independence, eval_thresholds schema
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root — extends Phase 0)

```text
modelserver/                       # lean serving image (onnxruntime + numpy + tokenizers; NO torch)
├── app.py                         # REPLACE stub: lifespan loads + SHA-verifies artifact (refuse-to-boot); /healthz; /predict
├── categorizer.py                 # NEW: load ONNX + tokenizer, run inference, calibrate, apply per-category thresholds, top-k
├── config.py                      # NEW: typed settings (extra='forbid') — artifact path, expected SHA-256, thresholds path
├── schemas.py                     # NEW: PredictRequest / PredictResponse (category, confidence, alternatives[], low_confidence)
├── logging.py                     # NEW: structlog JSON + request-id (mirror backend) + per-predict span (latency)
├── artifacts/                     # committed via Git LFS — the pinned foundation artifact
│   ├── categorizer.onnx           # LFS — the served model (winner export)
│   ├── tokenizer.json             # tokenizer for the served model
│   └── model_card.md              # data hash, metrics, freeze policy, pinned SHA-256
├── pyproject.toml                 # add `tokenizers`; keep lean (no torch/transformers/sklearn)
├── Dockerfile                     # mount/copy artifacts/; unchanged leanness
└── tests/                         # NEW pytest: predict contract, validation errors, refuse-to-boot (fixture ONNX)

training/                          # offline (Colab GPU) + CPU-runnable classical path; torch lives ONLY here/Colab
├── prepare_dataset.py             # NEW: Kaggle set → coarse taxonomy via consolidation map → fixed-seed stratified split + frozen holdout + manifest
├── taxonomy.yaml                  # NEW: locked ~10–15 categories + source→taxonomy consolidation map
├── train_baseline.py             # NEW: TF-IDF+LR (CPU, reproducible) → metrics + skl2onnx export
├── eval_zeroshot.py               # NEW: Gemini zero-shot baseline over the dataset (prompt from prompts/)
├── export_onnx.py                 # NEW: winner → ONNX + tokenizer + SHA-256 + model card
├── gate_holdout.py                # NEW: stack-independent gate — macro-F1(champion) vs baseline on holdout vs eval_thresholds
├── data/
│   ├── holdout.parquet            # LFS — frozen holdout (gate-only)
│   └── split_manifest.json        # committed — seeds, row counts, content hashes (reproducibility proof)
└── notebooks/
    └── categorizer_finetune.ipynb # NEW: Colab GPU DistilBERT fine-tune (the developer's offline deliverable)

prompts/
└── categorizer_zeroshot.md        # NEW: Gemini zero-shot classification prompt (Art. IV — file-based)

eval_thresholds.yaml               # FILL categorizer block: macro_f1_min (seeded floor), beat_baseline_margin, per-class threshold map, max_inference_latency_ms
.github/workflows/ci.yml           # ADD job `categorizer-gate` (LFS checkout → training/gate_holdout.py)
docs/DECISIONS.md                  # APPEND: three-way numbers, winner rule, threshold rule, seeded floor, serve-from-LFS-not-MinIO rationale
```

**Structure Decision**: Extend the Phase 0 monorepo in place. Real code fills the
existing `modelserver/` and `training/` trees — the Phase 0 file headers are the
map. The serving image gains exactly one lean dependency (`tokenizers`); torch is
confined to Colab/`trainer`. The frozen holdout and ONNX artifacts ride existing
LFS patterns (`*.onnx`, `*.parquet`). A new stack-independent CI job runs the gate.
No new top-level directories, no DB migration.

## Complexity Tracking

> No constitutional violations. Section intentionally empty.

## Key decisions deferred to /speckit-tasks

- Exact task ordering of the **human-in-the-loop Colab step**: the agent builds the
  full harness (prep, baseline, zero-shot, export, server, gate) and proves gate
  mechanics with the classical baseline; the developer runs the notebook to produce
  the champion artifact + real numbers, which are then committed (LFS) and recorded.
- Whether the classical baseline also ships as a committed fallback artifact for the
  gate's "beat baseline" comparison input.
