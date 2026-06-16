# training/

Offline training pipeline for the Raseed categorizer (Phase 2).

## Dataset provenance

**Source**: `laramee26openBankTransactionData.xlsx` — a publicly available **UK / GBP**
open banking transaction dataset. (The original plan named a Kaggle USA set; it turned
out to have synthetic merchant names with no learnable signal and was replaced on
2026-06-16 — see `docs/DECISIONS.md`.)

**Who provides it**: The developer. The dataset is **never committed** (size + licensing).

**How to acquire it**: download the `.xlsx` and drop it into `training/data/raw/`.
`prepare_dataset.py` auto-detects the first `*.xlsx` (then `*.csv`) in that directory.

**Expected path**: `training/data/raw/` (git-ignored; see top-level `.gitignore`).

**Data cleaning (the preprocessing deliverable)** — all in `prepare_dataset.py`,
recorded in `docs/DECISIONS.md`:
- drop null-Category rows;
- apply the consolidation map → 18-category locked taxonomy (`taxonomy.yaml` v2.0.0);
- drop singleton categories; merge overlaps;
- down-sample the repeated `SAVE THE CHANGE` string (1,165 → 150) so `savings` can't dominate;
- input text = `Transaction Description` + bracketed `Transaction Type` code.

The prep script (`prepare_dataset.py`) reads from that path. Everything except the
prep *run itself* is buildable before the data lands:

- `modelserver/` (model-server against fixture ONNX) — no data needed
- `training/gate_holdout.py` (gate mechanism against stand-ins) — no data needed
- `training/train_baseline.py`, `training/eval_zeroshot.py`, `training/export_onnx.py` — code is ready; runs need the split (T008)
- `training/notebooks/categorizer_finetune.ipynb` — Colab GPU step, developer-run after split exists

## Committed data artifacts

These are committed via **Git LFS** (see `.gitattributes`) and checked in after prep runs:

- `training/data/holdout.parquet` — frozen holdout (gate-only; touched only by `gate_holdout.py`)
- `training/data/split_manifest.json` — reproducibility proof (seeds, counts, content hashes)
- `training/data/baseline.onnx` — the classical baseline the CI gate scores against the champion
- `modelserver/artifacts/categorizer.onnx` — the served champion (SHA-pinned in `config.py`)

Everything else under `training/data/` (train/val/test parquets, prediction files,
`*_results.json`, `operating_thresholds.json`) is regenerable and git-ignored.

## Directory layout

```
training/
├── requirements.txt          # offline + gate deps (torch/transformers: Colab only)
├── taxonomy.yaml             # locked 18-category taxonomy (v2.0.0) + consolidation map
├── prepare_dataset.py        # raw → split + frozen holdout + manifest
├── train_baseline.py         # TF-IDF + LR → ONNX via skl2onnx
├── eval_zeroshot.py          # Gemini zero-shot baseline
├── export_onnx.py            # winner → ONNX + tokenizer + model card
├── gate_holdout.py           # CI gate: champion vs baseline on holdout
├── data/
│   ├── raw/                  # ← DROP DATASET HERE (git-ignored)
│   ├── holdout.parquet       # LFS — frozen holdout
│   └── split_manifest.json   # reproducibility proof
├── notebooks/
│   └── categorizer_finetune.ipynb  # Colab GPU DistilBERT fine-tune (developer runs)
└── tests/
    └── test_split_reproducible.py  # deterministic-split test (SC-009)
```

## Build order

1. Developer drops dataset → `training/data/raw/`
2. `python training/prepare_dataset.py` — produces split + holdout + manifest
3. `python training/train_baseline.py` — CPU-runnable classical baseline
4. `python training/eval_zeroshot.py` — Gemini zero-shot comparison
5. Developer runs `training/notebooks/categorizer_finetune.ipynb` on **Colab GPU** → champion
6. `python training/export_onnx.py` — export winner + per-class thresholds
7. Commit `modelserver/artifacts/` (LFS) and update `eval_thresholds.yaml`
8. CI `categorizer-gate` job verifies the champion on the holdout

## Model-server champion swap procedure

After a new champion is exported:
1. Copy `categorizer.onnx` + `tokenizer.json` to `modelserver/artifacts/`
2. Update `artifact_sha256` in `modelserver/config.py` to match the new artifact
3. Update `modelserver/artifacts/model_card.md` with new metrics
4. Fill `eval_thresholds.yaml` categorizer block with real numbers
5. CI gate must pass before merging
