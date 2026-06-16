# Contract: CI gate #1 — categorizer quality (Phase 2)

The first of the constitution's eight gates goes live. It runs **stack-independently**
in CI from committed artifacts (Git LFS), never from a running service. *(Art. V)*

## Inputs (all committed; LFS checkout)
- `training/data/holdout.parquet` — the frozen holdout (gate-only; never used in
  training/selection/threshold tuning). *(FR-003)*
- The **champion** (`modelserver/artifacts/categorizer.onnx` + tokenizer) and the
  **classical baseline** model/predictions.
- `eval_thresholds.yaml` → `categorizer` block (the committed bars).
- `training/taxonomy.yaml` (label space).

## Gate rule *(FR-020, FR-020a, FR-022)*
Let `C` = champion macro-F1 on the holdout, `B` = classical baseline macro-F1.
**PASS iff all hold:**
1. `C − B ≥ beat_baseline_margin`  *(always binding — works before any champion number exists)*
2. `C ≥ macro_f1_min`  *(the ratcheting absolute floor)*
3. `min(per_class_F1) ≥ min_per_class_f1`  *(no class collapses — imbalance guard)*
4. measured single-call latency ≤ `max_inference_latency_ms`

Any failure **blocks merge**. *(SC-005)*

## Ratcheting floor *(FR-020a)*
`macro_f1_min` is seeded from the first champion's measured holdout macro-F1 minus a
small committed tolerance, and is **only ever raised**, never lowered to admit a
weaker model. A PR that lowers it is rejected in review.

## Stack independence *(FR-021, Art. V)*
The gate (`training/gate_holdout.py`) loads models + holdout from the filesystem
(LFS), computes metrics, and exits non-zero on failure. It **MUST NOT** call
`modelserver`, the backend, or any running service, and MUST NOT require compose.

## CI wiring
New job `categorizer-gate` in `.github/workflows/ci.yml`:
- `actions/checkout@v4` with `lfs: true`.
- Install the gate's lean eval deps (onnxruntime, numpy, pandas/pyarrow,
  scikit-learn for metrics only — gate-side, never in the serving image).
- Run `python training/gate_holdout.py`; non-zero exit fails the job.

## Decision record *(Art. V)*
DECISIONS.md records: the three-way comparison numbers (classical / DistilBERT /
zero-shot: macro-F1, per-class F1, latency, cost), the winner-selection rule, the
per-class operating-threshold rule, and the seeded `macro_f1_min` floor with its
tolerance.
