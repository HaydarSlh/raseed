# Phase 1 Data Model — Categorizer

**No database tables and no Alembic migration this phase.** A prediction is computed
and returned, never persisted; the `transactions` columns that will store a category
(`provenance`/`confidence`/`needs_review`) already exist from Phase 1 and are written
by Phase 3 ingestion. The "data model" here is the set of **schemas, config, and
artifact shapes** the categorizer introduces.

## 1. Predict request / response (model-server API contract)

**PredictRequest**
| Field | Type | Rules |
|-------|------|-------|
| `description` | string | required; trimmed length 1..512; not whitespace-only |
| `top_k` | int | optional; default 3; range 1..5 |

**PredictResponse**
| Field | Type | Rules |
|-------|------|-------|
| `category` | string | the primary category; MUST be a member of the locked taxonomy |
| `confidence` | float | calibrated, range [0,1] |
| `alternatives` | list[CategoryScore] | length ≤ `top_k`, descending by score, excludes the primary or includes it at rank 0 (contract fixes one — see predict-api.md) |
| `low_confidence` | bool | true iff `confidence` < the predicted category's operating threshold (or the category is a sentinel always-review class) |

**CategoryScore**: `{ category: string (∈ taxonomy), score: float [0,1] }`

Validation failures → structured error (HTTP 422 shape), never a stack trace.

## 2. Locked taxonomy (`training/taxonomy.yaml`)

| Element | Type | Rules |
|---------|------|-------|
| `version` | string | bumped when the category set changes |
| `categories` | list[string] | the locked ~10–15 category names (closed set) |
| `consolidation_map` | map[string→string] | source dataset category → taxonomy category; total over all source labels; unmapped source labels → `other` deterministically |

Invariant: the model's output label space == `categories`. The same file is read by
prep, training, and the model-server (to validate outputs).

## 3. Evaluation thresholds (`eval_thresholds.yaml` → `categorizer` block)

| Key | Type | Meaning |
|-----|------|---------|
| `macro_f1_min` | float | the **ratcheting absolute floor**; seeded from the first champion's holdout macro-F1 minus tolerance; only ratchets up |
| `beat_baseline_margin` | float | required champion − baseline macro-F1 gap (always binding) |
| `min_per_class_f1` | float | gate fails if any taxonomy class falls below this on the holdout |
| `max_inference_latency_ms` | int | served p95 single-call bound (gate-checked) |
| `operating_thresholds` | map[string→float\|`"always_review"`] | per-category confidence cut for ≥97% precision; sentinel for sparse classes |

(Phase 0 ships these as `null` placeholders; this phase fills them with numbers
backed by DECISIONS.md.)

## 4. Model card (`modelserver/artifacts/model_card.md`)

Required recorded fields: `data_hash` (holdout content hash from the split manifest),
`metrics` (champion macro-F1 + per-class F1 + latency + cost; plus the baseline and
zero-shot numbers for the three-way record), `freeze_policy` (**full fine-tune for
the foundation model; partial unfreeze for in-stack retrains in Phase 5**),
`artifact_sha256` (pinned hash that MUST equal the served artifact's SHA-256),
`taxonomy_version`, `calibration_method`, `seeds`.

## 5. Split manifest (`training/data/split_manifest.json`)

| Field | Type | Meaning |
|-------|------|---------|
| `seeds` | object | every seed used (split, shuffle, training) |
| `counts` | map[split→map[category→int]] | per-class row counts for train/val/test/holdout |
| `hashes` | map[split→string] | content hash per split; `holdout` hash == model card `data_hash` |
| `taxonomy_version` | string | the taxonomy the split was built against |
| `source_dataset` | object | name + source content hash of the raw Kaggle input |

Reproducibility check (SC-009): re-running `prepare_dataset.py` with the same seeds
reproduces identical `hashes`.

## 6. Served artifact bundle (`modelserver/artifacts/`, Git LFS)

- `categorizer.onnx` — the model graph (+ embedded temperature scalar for the neural
  champion, or full TF-IDF+LR pipeline via skl2onnx for a classical winner).
- `tokenizer.json` — WordPiece tokenizer for the neural champion (loaded by the
  `tokenizers` lib; absent/ignored for a classical winner).
- `model_card.md` — §4 above.

Relationships: `model_card.artifact_sha256` ↔ SHA-256(`categorizer.onnx`) [boot
guard]; `model_card.data_hash` ↔ `split_manifest.hashes.holdout`; taxonomy version
consistent across `taxonomy.yaml`, the artifact, and the model card.
