# Phase 0 Research — Categorizer (Trained Offline, Served Lean)

All "NEEDS CLARIFICATION" from Technical Context are resolved below. Each item is
Decision / Rationale / Alternatives. Numbers that depend on training land in
`eval_thresholds.yaml` + `docs/DECISIONS.md` once the developer's Colab run
produces them (per the spec's clarified ratcheting-floor approach).

## R1 — Source dataset & locked taxonomy

- **Decision**: Use the `laramee26openBankTransactionData.xlsx` dataset (UK/GBP open
  banking transactions). Consolidate its native categories into a **cleaned, locked
  taxonomy of 18 categories** via a version-controlled map in `training/taxonomy.yaml`
  (savings, amazon, groceries, bills, cash, dine_out, income, travel, other_shopping,
  services, entertainment, investment, insurance, home_improvement, hotels, clothes,
  mortgage, fitness). Every served prediction is a member of this set.
  **History**: the original plan named the Kaggle USA Banking Transactions set, but its
  merchant names were synthetic (no learnable signal). Switched to the laramee UK set
  on 2026-06-16 — see `docs/DECISIONS.md` for the full cleaning/merge/down-sample log.
- **Rationale**: Clarified in spec (Session 2026-06-14); target was ~10–15 coarse
  buckets for more samples per class. Real cleanup landed at 18 to preserve thin
  watch-classes (fitness/clothes/hotels) and keep mortgage/insurance distinct. Coarse
  buckets give more samples per class → higher per-class F1, an easier-to-pass gate,
  and a meaningful per-class precision threshold. The map makes consolidation
  deterministic and auditable.
- **Alternatives**: Fine ~25–40 categories (sparser classes, harder gate);
  dataset-native as-is (inherits imbalance) — both rejected for v1.

## R2 — Reproducible split & frozen holdout

- **Decision**: `prepare_dataset.py` performs a **stratified train/val/test split
  with fixed seeds**, then carves a **frozen holdout** (a fixed slice of test, or a
  separate stratified draw) written to `training/data/holdout.parquet` (Git LFS).
  Emit `training/data/split_manifest.json` recording seeds, per-class row counts,
  and content hashes of each split. The holdout's content hash is the **data hash**
  echoed in the model card.
- **Rationale**: Byte-for-byte reproducibility (SC-009) needs pinned seeds + pinned
  library versions + a recorded manifest. Stratification keeps imbalanced classes
  represented in val/holdout so per-class F1 is measurable.
- **Alternatives**: Random unseeded split (not reproducible); time-based split (no
  reliable timestamp in the dataset) — rejected.

## R3 — Three approaches & metrics

- **Decision**: Evaluate (a) **TF-IDF + logistic regression** (classical, CPU,
  fully reproducible), (b) **fine-tuned DistilBERT** (Colab GPU), (c) **Gemini
  zero-shot** (offline, prompt from `prompts/`). Metrics for each: macro-F1,
  per-class F1, single-call latency, cost per call. Record all three in
  DECISIONS.md; the winner (by the recorded rule — highest holdout macro-F1 subject
  to the latency bar) ships.
- **Rationale**: Brief mandate. The classical baseline is the gate's permanent
  comparison and is producible by the agent end-to-end; DistilBERT is the expected
  champion but requires GPU; zero-shot bounds "how far does a no-train LLM get."
- **Alternatives**: Skipping the classical baseline (then the gate has nothing to
  "beat") — rejected; it is the baseline.

## R4 — Confidence calibration

- **Decision**: Calibrate probabilities on the **validation** set so the precision
  threshold rule is meaningful: **temperature scaling** for the neural champion
  (single parameter, preserves ranking/accuracy), `predict_proba` + (optional)
  isotonic/Platt for the LR baseline. Record the calibration method + the
  reliability check in the model card.
- **Rationale**: Raw softmax/logit scores are over-confident; FR-008 requires
  calibrated confidence so "≥97% precision at threshold τ" actually holds in
  serving. Temperature scaling is the standard lightweight fix and bakes into the
  ONNX graph (a scalar divide on logits) → no serving complexity.
- **Alternatives**: Uncalibrated scores (threshold meaningless); full Bayesian /
  ensemble calibration (overkill) — rejected.

## R5 — Per-class operating threshold selection

- **Decision**: For each category, sweep candidate thresholds on **validation** and
  pick the **highest confidence threshold that still holds ≥97% precision** for that
  category. Categories with too few validation samples to establish the rule get a
  sentinel meaning **always route for review** (never auto-accepted). Write the
  resulting `category → threshold` map (plus sentinels) to the `categorizer` block
  of `eval_thresholds.yaml`.
- **Rationale**: Clarified in spec. A single global cut cannot hold 97% precision
  across imbalanced classes; per-class thresholds deliver the guarantee where data
  allows and fail safe (review) where it does not.
- **Alternatives**: Single global threshold (leaks on rare classes); per-class with
  a guessed cut for sparse classes (unvalidatable) — rejected.

## R6 — ONNX export & torch-free tokenization

- **Decision**: Export the winner to **ONNX**. For a DistilBERT champion, ship
  `tokenizer.json` and tokenize at serve time with the **`tokenizers`** library (the
  Rust-backed HF tokenizer — torch-free, ~a few MB); the ONNX graph holds the model
  + the temperature scalar. For a TF-IDF+LR winner, **skl2onnx** embeds the
  vectorizer + classifier so the serving runtime is pure onnxruntime + numpy.
  Either way the model-server carries **no torch, no transformers, no sklearn**.
- **Rationale**: Art. III leanness. `tokenizers` is the only way to reproduce
  WordPiece without `transformers`/torch; skl2onnx removes sklearn from the serve
  path for the classical case. Both keep the image lean.
- **Alternatives**: Bundle `transformers` for tokenization (drags torch-adjacent
  weight, violates leanness); reimplement WordPiece by hand (error-prone) —
  rejected.

## R7 — Artifact delivery: LFS for CI, mounted for serving (MinIO deferred)

- **Decision**: Commit `categorizer.onnx`, `tokenizer.json`, and `holdout.parquet`
  via **Git LFS** (existing `.gitattributes` patterns cover `*.onnx` / `*.parquet`).
  CI gets them via LFS checkout. The **model-server mounts the pinned artifact from
  its image** (`modelserver/artifacts/`) and verifies SHA-256 at boot.
  **MinIO-sourced loading + hot reload is deferred to Phase 5** (DESIGN C), where
  runtime artifact rotation first exists; `minio.py` stays a stub until then.
- **Rationale**: The Phase 2 brief requires refuse-to-boot on a pinned artifact, not
  runtime rotation. There is nothing to rotate yet, so a mounted, immutable,
  SHA-pinned artifact is the minimal surface (YAGNI) and still honors "MinIO holds
  artifacts only" (MinIO is simply untouched this phase). The decision + trade-off
  is recorded in DECISIONS.md so Phase 5 knows to add the MinIO load+reload path.
- **Alternatives**: Seed MinIO from LFS via a one-shot job + load-from-MinIO now
  (forward-compatible but adds a job, a MinIO client, and a load path with nothing
  to rotate) — deferred to Phase 5; bake artifact but skip SHA verify (violates
  refuse-to-boot) — rejected.

## R8 — Refuse-to-boot mechanism

- **Decision**: On startup the model-server reads the artifact, computes its
  **SHA-256**, and compares to the **expected hash pinned in typed settings**
  (sourced from the model card). On a missing artifact OR a hash mismatch the
  process **fails to become ready / exits non-zero** — it never serves an unknown
  model. `/healthz` reports ready **only** while a verified model is loaded.
- **Rationale**: Art. III ("servers MUST refuse to boot on a hash mismatch") + FR-013.
  Activates the guard the Phase 0 stub deliberately left off.
- **Alternatives**: Warn-and-serve on mismatch (violates the invariant); verify
  lazily on first request (a bad artifact could serve briefly) — rejected.

## R9 — CI gate #1

- **Decision**: New CI job `categorizer-gate` (LFS-enabled checkout). It runs
  `training/gate_holdout.py`, which loads the **champion** and **classical baseline**
  predictions on `holdout.parquet`, computes macro-F1 for each, and **passes only
  if** champion_macroF1 − baseline_macroF1 ≥ `beat_baseline_margin` **AND**
  champion_macroF1 ≥ `macro_f1_min` (the ratcheting floor). It also asserts no
  per-class F1 collapses below `min_per_class_f1` and latency ≤
  `max_inference_latency_ms`. All inputs are committed; **no compose, no running
  stack**. A failure blocks merge.
- **Rationale**: Brief + Art. V + spec FR-020/020a/021/022. The margin makes the
  gate meaningful from day one (no champion number needed); the floor seeds from the
  first champion and only ratchets up.
- **Alternatives**: Gate inside an integration job that boots modelserver (violates
  "CI never depends on the stack") — rejected.

## R10 — Human-in-the-loop Colab training

- **Decision**: Foundation DistilBERT fine-tuning is an **offline developer step in
  Colab on GPU**; `notebooks/categorizer_finetune.ipynb` is the deliverable. The
  agent builds everything else and validates the harness (split test +
  classical-baseline run + gate mechanics). The developer runs the notebook,
  produces `categorizer.onnx` + `tokenizer.json` + the champion's macro-F1 /
  per-class F1 / latency / cost, commits them (LFS), and the numbers are written to
  DECISIONS.md + `eval_thresholds.yaml` (seeding the floor).
- **Rationale**: The brief mandates Colab GPU for foundation training; CI/agents
  cannot run GPU training. Separating "harness the agent builds" from "champion the
  developer trains" keeps the phase executable and honest.
- **Alternatives**: Train DistilBERT in CI/agent on CPU (too slow, not the mandated
  path); ship without the champion (no gate-passing winner) — rejected.

## R11 — Latency & cost measurement

- **Decision**: Measure **single-call inference latency** (median + p95) for each
  approach under onnxruntime on CPU; **cost per call** = ~$0 for self-hosted
  classical/neural, and the metered Gemini token cost for zero-shot (via the adapter
  pricing). Record all in DECISIONS.md; enforce the served latency bar via
  `max_inference_latency_ms` in the gate and the p95<200ms target (SC-001).
- **Rationale**: SC-006 requires concrete latency + cost for all three; SC-001 sets
  the served bar. onnxruntime-CPU is the realistic serving condition.
- **Alternatives**: GPU latency numbers (not the serving condition) — rejected.
