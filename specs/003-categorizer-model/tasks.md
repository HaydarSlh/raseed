---
description: "Task list for Phase 2 — Categorizer: trained offline, served lean"
---

# Tasks: Categorizer — Trained Offline, Served Lean

**Input**: Design documents from `specs/003-categorizer-model/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED. The constitution (Art. III/V), the brief's acceptance criteria,
and the spec mandate CI-backed proofs — the model-server `/predict` + refuse-to-boot
tests, the deterministic-split test, and the gate's pass/fail mechanism. They ship
alongside their implementation (the security-style proofs — refuse-to-boot, gate
degraded-model — must fail before the mechanism exists and pass after).

**Organization**: Setup + Foundational build the shared data spine (taxonomy +
deterministic split + frozen holdout). The story phases deliver the three
independently testable outcomes: the lean served `/predict` (US1), the CI quality
gate (US2), and reproducible training + provenance (US3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (story-phase tasks only)
- All work extends the existing Phase 0 `modelserver/` and `training/` trees; paths
  are repo-relative. Phase 0 file headers are the file map.

---

## ⚠️ Build-order reality (read before starting)

The spec prioritizes US1/US2 (P1, the headline outcomes) over US3 (P2, the means).
But the **artifact and the real numbers** US1/US2 ultimately need are US3 outputs,
and the champion is produced by a **human-in-the-loop Colab GPU run** (T027). To
keep every story independently testable, US1 is built and tested against a tiny
**fixture ONNX**, and US2's gate is built and tested against **stand-in models** —
both go green without the champion. The *real* served artifact (US1 in compose) and
the *real* CI-gate green (US2) are achieved after US3 produces and commits the
champion. The **raw Kaggle dataset is provided by the developer** (T006); all
non-data-dependent work is buildable before it lands. See **Dependencies &
Execution Order** for the recommended sequence.

---

## Phase 1: Setup

**Purpose**: Dependencies, dataset provenance, and scaffolding needed by every story.

- [x] T001 Update `modelserver/pyproject.toml`: add `tokenizers`, `structlog`, `pydantic-settings`; keep the serving image lean — **no `torch`/`transformers`/`scikit-learn`** in runtime deps (Art. III).
- [x] T002 [P] Add `training/requirements.txt` (offline + gate deps): `scikit-learn`, `onnx`, `skl2onnx`, `onnxruntime`, `numpy`, `pandas`, `pyarrow`, `datasets`, `google-genai`, `pyyaml`; comment that `torch`/`transformers` are **Colab-only** (notebook), never installed in CI or serving.
- [x] T003 [P] Create `prompts/categorizer_zeroshot.md` — the Gemini zero-shot classification prompt (file-based, Art. IV); lists the locked taxonomy and the output format.
- [x] T004 [P] Verify/extend `.gitattributes` LFS coverage for the artifact bundle (`modelserver/artifacts/*.onnx`, `tokenizer.json`) and `training/data/holdout.parquet` (parquet already covered); confirm `git lfs` tracks them.
- [x] T005 [P] Create test scaffolding: `modelserver/tests/__init__.py`, `modelserver/tests/fixtures/.gitkeep`, `training/tests/__init__.py`.
- [x] T006 [P] **Dataset provenance**: add a `training/README.md` (or section) documenting that the raw **Kaggle USA Banking Transactions** dataset is provided by the developer — fetched via the Kaggle API with the developer's credentials **or** dropped manually into `training/data/raw/` — and that the prep scripts read it from that path. Add `training/data/raw/` to `.gitignore` (the raw dataset is **never committed** — size/licensing). Note that all non-data-dependent work (model-server vs fixtures, gate mechanism vs stand-ins, all US3 code) is buildable before the data lands.

**Checkpoint**: deps resolve lean; prompt + LFS + test scaffolding exist; dataset path + provenance documented and git-ignored.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared data spine every story depends on. **Blocks US1/US2/US3.**

**⚠️ CRITICAL**: No story work begins until this phase is complete. (Code is
buildable now; the *runs* of T008 await the developer-provided dataset from T006.)

- [x] T007 Author `training/taxonomy.yaml`: `version`, the locked **~10–15 coarse categories** (closed set), and a total `consolidation_map` (source Kaggle category → taxonomy category; unmapped → `other`) per data-model.md §2.
- [x] T008 Implement `training/prepare_dataset.py`: read the raw dataset from `training/data/raw/` (T006), apply the consolidation map, produce a **fixed-seed stratified train/val/test split** + a **frozen `training/data/holdout.parquet`** (Git LFS) + `training/data/split_manifest.json` (seeds, per-class counts, content hashes, taxonomy_version, source hash) per data-model.md §5. Depends on T007.
- [x] T009 [P] Deterministic-split test in `training/tests/test_split_reproducible.py` — re-run prep with the fixed seeds and assert identical per-split content hashes; assert the `holdout` hash is stable (SC-009). Depends on T008.

**Checkpoint**: taxonomy locked; split + frozen holdout reproducible; data hash defined.

---

## Phase 3: User Story 1 - Categorize via the served model (Priority: P1) 🎯 MVP

**Goal**: The lean model-server returns category + calibrated confidence + top-k for
a description over HTTP, is ready only with a verified model, and **refuses to boot**
on a missing artifact or SHA-256 mismatch.

**Independent Test**: With a fixture ONNX, POST descriptions → category ∈ taxonomy,
confidence ∈ [0,1], ranked alternatives, `low_confidence` flag; `/healthz` ready;
missing/tampered artifact → server refuses to boot (quickstart Scenarios 1–3, 6).

### Tests for User Story 1 (write first; must fail before implementation) ⚠️

- [x] T010 [P] [US1] `/predict` contract test in `modelserver/tests/test_predict.py` — category ∈ taxonomy, calibrated confidence ∈ [0,1], `alternatives` ranked & includes primary at rank 0, per-category `low_confidence` flag (predict-api.md, SC-001).
- [x] T011 [P] [US1] Refuse-to-boot test in `modelserver/tests/test_refuse_to_boot.py` — missing artifact AND SHA-256 mismatch each cause non-ready/non-zero boot; `/healthz` never reports ready without a verified model (model-artifact.md, SC-004).
- [x] T012 [P] [US1] Validation-error test in `modelserver/tests/test_validation.py` — empty/whitespace/oversized `description` and out-of-range `top_k` → structured 422, never a stack trace (FR-017).
- [x] T013 [P] [US1] Lean-image guard test in `modelserver/tests/test_lean_image.py` — assert `torch`/`transformers`/`scikit-learn` are not importable / not in the serving deps (SC-007, Art. III).
- [x] T014 [P] [US1] Build a tiny deterministic **fixture ONNX** + `tokenizer.json` + a small `operating_thresholds` map under `modelserver/tests/fixtures/` for the tests above (no torch — emit a trivial onnx via `onnx` helper or skl2onnx on a 2-row toy set).

### Implementation for User Story 1

- [x] T015 [P] [US1] `modelserver/config.py` — typed `Settings` (`extra='forbid'`): artifact path, **expected SHA-256**, tokenizer path, thresholds/taxonomy path, host/port; fail-fast on missing required value.
- [x] T016 [P] [US1] `modelserver/schemas.py` — `PredictRequest`, `PredictResponse`, `CategoryScore` with validation rules per data-model.md §1.
- [x] T017 [P] [US1] `modelserver/logging.py` — structlog JSON + request-id middleware + a per-predict span carrying latency; never log the raw description at info level (Art. II/V).
- [x] T018 [US1] `modelserver/categorizer.py` — implement the thin **"get current artifact" seam** (`get_current_artifact() -> ArtifactRef`, a **mounted-file provider** this phase per FR-016/contract) and load ONNX (onnxruntime) + tokenizer (`tokenizers`) **through it**; run inference, apply calibration, compute top-k and the **per-category** low-confidence flag against `operating_thresholds`; outputs constrained to the taxonomy. Depends on T015, T016.
- [x] T019 [US1] `modelserver/app.py` — **replace the Phase 0 stub**: lifespan resolves the artifact **via the seam**, computes SHA-256, **refuses to boot on missing/mismatch** (boot + hash-verify logic source-agnostic — never references a concrete source); `/healthz` ready only with a verified model; `POST /predict`; domain-exception→structured-error handlers. Depends on T017, T018.
- [x] T020 [US1] `modelserver/Dockerfile` — ensure `artifacts/` is present in the image and lean deps install; `docker build` green; image carries no torch/transformers/sklearn. Depends on T001.

**Checkpoint**: model-server serves `/predict` and refuses to boot, proven against the fixture (MVP).

---

## Phase 4: User Story 2 - Prove quality before ship (Priority: P1)

**Goal**: A CI gate evaluates the candidate on the frozen holdout and passes only if
it beats the classical baseline by a committed margin AND clears the ratcheting
macro-F1 floor — run entirely from committed artifacts, never the running stack.

**Independent Test**: With stand-in good/degraded models the gate passes/fails
correctly and never starts any service; a degraded champion blocks merge (quickstart
Scenario 4, SC-005).

### Tests for User Story 2 (write first) ⚠️

- [x] T021 [P] [US2] Gate mechanism test in `training/tests/test_gate.py` — feed two stand-in result sets (champion beats baseline by margin & ≥ floor → PASS; degraded or below-floor or a collapsed per-class F1 → FAIL/non-zero); assert the gate makes **no** network/service calls (FR-021, SC-005).

### Implementation for User Story 2

- [x] T022 [US2] Implement `training/gate_holdout.py` — load champion + classical-baseline predictions on `holdout.parquet`, compute macro-F1 each; **PASS iff** `C−B ≥ beat_baseline_margin` AND `C ≥ macro_f1_min` AND `min(per_class_F1) ≥ min_per_class_f1` AND single-call latency ≤ `max_inference_latency_ms`; exit non-zero on failure; reads `eval_thresholds.yaml` + `taxonomy.yaml`; **no stack** (ci-gate.md). NOTE: `max_inference_latency_ms` is a **single-call** bound — distinct from the **p95** figure measured in T033. Depends on T008.
- [x] T023 [US2] Define the `categorizer` block schema in `eval_thresholds.yaml` — keys `macro_f1_min`, `beat_baseline_margin`, `min_per_class_f1`, `max_inference_latency_ms`, `operating_thresholds` (placeholders + comments; real numbers land in US3) per data-model.md §3.
- [x] T024 [US2] Add CI job `categorizer-gate` to `.github/workflows/ci.yml` — `actions/checkout@v4` with `lfs: true`, install the gate deps (onnxruntime, numpy, pandas/pyarrow, scikit-learn for metrics only), run `python training/gate_holdout.py`; non-zero exit blocks merge; never boots compose (Art. V). Depends on T022.

**Checkpoint**: gate logic + CI job green against stand-ins (real green awaits US3 artifacts).

---

## Phase 5: User Story 3 - Reproducible training & provenance (Priority: P2)

**Goal**: Three approaches compared on real numbers, the winner exported to ONNX with
calibrated confidence and per-class thresholds, and a model card recording data hash,
metrics, freeze policy, and the pinned SHA-256 — all reproducible.

**Independent Test**: Re-run prep → identical split; the three-way comparison exists
with concrete numbers; the model card lists data hash/metrics/freeze policy and a
SHA matching the served artifact (quickstart Scenarios 5, 7).

### Implementation for User Story 3

- [x] T025 [P] [US3] Implement `training/train_baseline.py` — TF-IDF + logistic regression on the split; metrics (macro-F1, per-class F1, single-call latency, cost≈0); calibrate (`predict_proba`/isotonic); export the baseline pipeline to ONNX via **skl2onnx** (serve-path pure onnxruntime). Depends on T008.
- [x] T026 [P] [US3] Implement `training/eval_zeroshot.py` — Gemini zero-shot over the dataset using `prompts/categorizer_zeroshot.md` through the adapter pattern (timeout/retry, 4xx not retried); record macro-F1, per-class F1, latency, **token cost** (Art. IV/V). Depends on T003, T007.
- [x] T027 [US3] Author `training/notebooks/categorizer_finetune.ipynb` — Colab GPU **DistilBERT fine-tune** on the split (full fine-tune), temperature-scaling calibration on validation; emits the champion + `tokenizer.json` + its macro-F1/per-class-F1/latency/cost. **HUMAN-IN-THE-LOOP: the developer runs this on Colab GPU** (R10). Depends on T008.
- [x] T028 [US3] Implement `training/export_onnx.py` — take the winner (by the recorded rule), export `categorizer.onnx` (embed temperature scalar) + `tokenizer.json`, compute SHA-256, and select **per-category operating thresholds** (highest cut holding ≥97% precision on validation; **a category with < 20 validation samples → `always_review`**). Depends on T027 (champion) / T025 (baseline fallback).
- [x] T029 [US3] Write `modelserver/artifacts/model_card.md` — `data_hash` (=holdout hash), three-way `metrics`, `freeze_policy` (full fine-tune foundation; partial unfreeze for Phase 5 retrains), `artifact_sha256`, `taxonomy_version`, `calibration_method`, `seeds` (FR-018/FR-019). Depends on T028.
- [x] T030 [US3] Commit the champion bundle (`modelserver/artifacts/categorizer.onnx` + `tokenizer.json`) via **Git LFS**; set the pinned expected SHA-256 in `modelserver/config.py` to match the model card. Depends on T029. **⏳ AWAITS COLAB RUN (T027)**
- [x] T031 [US3] Fill the real `categorizer` numbers in `eval_thresholds.yaml` — seed `macro_f1_min` = champion holdout macro-F1 − committed tolerance, set `beat_baseline_margin`, `min_per_class_f1`, `max_inference_latency_ms`, and the `operating_thresholds` map from T028. Depends on T028. **⏳ AWAITS COLAB RUN (T027)**
- [x] T032 [US3] Append `docs/DECISIONS.md` — the three-way comparison numbers (TF-IDF+LR / DistilBERT / Gemini zero-shot: macro-F1, per-class F1, latency, cost), the winner-selection rule, the per-class threshold rule (incl. the < 20-sample always_review trigger), and **the actual ratchet tolerance value used to seed `macro_f1_min`, with rationale** (A1). (The serve-from-LFS / MinIO-deferral + seam decision and the N=20 rule are already recorded — 2026-06-15 rows.) Depends on T025, T026, T027, T031. **⏳ AWAITS COLAB RUN (T027)**

**Checkpoint**: real artifact + real numbers committed; the US2 CI gate now goes green for real; US1 serves the real champion in compose.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T033 [P] Run the full `quickstart.md` validation (Scenarios 1–7) against the built image and committed artifacts; **own the p95 measurement of record** — a small latency benchmark over a batch of representative inputs reporting **p95 vs the 200 ms target (SC-001)**, distinct from the gate's single-call bound. Confirm acceptance criteria + contracts. **⏳ AWAITS CHAMPION ARTIFACT (T030)**
- [x] T034 [P] Ensure `ruff` + `mypy` green for `modelserver/` and `training/`; extend `training/README.md` and add a short `modelserver/` serving note (boot, predict, the Colab champion-swap procedure).
- [x] T035 Refresh the knowledge graph: `graphify update .`.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no deps — start immediately. T006 (dataset provenance) gates the *runs* of any data-dependent task, not their code.
- **Foundational (Phase 2)**: depends on Setup — **blocks all stories**. T008 needs T007 (taxonomy) + the raw data path (T006); T009 needs T008.
- **US1 (P1)**: after Foundational. Built & tested against the **fixture ONNX** (T014) — independently testable without the champion or the dataset.
- **US2 (P1)**: after Foundational. Gate logic + CI job tested against **stand-ins** (T021) — independently testable. Real CI green requires US3 outputs (T030/T031).
- **US3 (P2)**: after Foundational. Produces the real artifact + numbers. Contains the **human-in-the-loop Colab step (T027)** and needs the developer-provided dataset (T006).
- **Polish (Phase 6)**: after the desired stories are complete.

### Real build-order (recommended sequence)

`Setup → Foundational code → US1 (fixture-tested server)` and `US2 gate mechanism (T021–T023)` are fully agent-buildable now. Once the developer provides the dataset (T006): run `T008/T009` → `US3 baseline + zero-shot (T025, T026)`. Then the **developer runs T027 (Colab)** → `US3 export/model-card/LFS/thresholds/DECISIONS (T028–T032)` → **US2 CI gate goes green for real (T024)** → `Polish (T033 quickstart+p95, T034, T035 graphify)`.

### Cross-task notes

- T014 fixture unblocks all US1 tests (T010–T013) without any trained model or dataset.
- T018/T019 load + verify the artifact **only through the "get current artifact" seam** (mounted-file provider now; Phase 5 swaps to store-by-SHA without touching boot logic).
- T022 gate reads the holdout (T008) and the thresholds schema (T023).
- T028 needs the champion (T027, human) — or falls back to the baseline (T025) to exercise export end-to-end before the champion lands.
- T030 pins the SHA the model-server verifies at boot (T019) — keep them in sync.

### Parallel opportunities

- Setup: T002, T003, T004, T005, T006 [P].
- US1 tests: T010, T011, T012, T013, T014 [P]; impl T015, T016, T017 [P] then T018→T019; T020 [P].
- US3: T025, T026 [P] (T027 is the human Colab step; T028–T032 serialize on the artifact).

---

## Implementation Strategy

### MVP first (US1)

1. Setup → Foundational (code).
2. US1 against the fixture ONNX → demo `/predict` + refuse-to-boot end-to-end.
3. **STOP and VALIDATE**: the lean server answers and refuses a bad artifact — the headline serving guarantee.

### Incremental delivery

1. Setup + Foundational → data spine ready (code now; runs after T006 data lands).
2. US1 → lean serving proven (fixture). 3. US2 gate mechanism vs stand-ins. 4. US3 baseline/zero-shot + **Colab champion** → real artifact + numbers. 5. US2 → gate green in CI on real artifacts. 6. Polish → quickstart + p95 + graphify refresh.

---

## Notes

- Serving stays lean: onnxruntime + numpy + `tokenizers` only; torch is Colab/`trainer`-only (Art. III).
- The frozen holdout is touched **only** by the gate (T022) — never by training/selection/threshold tuning.
- The Gemini zero-shot prompt lives in `prompts/` (Art. IV); it runs offline over the dataset, never user data.
- CI never depends on the running stack — the gate loads committed LFS artifacts (Art. V).
- The raw Kaggle dataset is developer-provided and never committed (`training/data/raw/` git-ignored).
- Commit on the `003-categorizer-pipeline` branch; end with `graphify update .`.
- No Alembic migration this phase (no new DB tables).
