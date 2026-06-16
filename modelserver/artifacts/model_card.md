# Model Card — Raseed Transaction Categorizer

**Status**: Phase 2 baseline champion — TF-IDF+LR on the cleaned laramee open-bank
dataset. DistilBERT fine-tune (Colab/T027) is the expected upgrade but not yet run;
the classical baseline ships as champion because it already clears the gate.

## Artifact

| Field | Value |
|-------|-------|
| `artifact_sha256` | `3f5dc0e0edb4efd017fc515785f2daf2976314738ff14ef733f121c25f45b331` |
| `taxonomy_version` | `2.0.0` |
| `calibration_method` | `isotonic` (CalibratedClassifierCV, cv="prefit" on val split) |
| `seeds` | split=42, shuffle=7 |

## Data

| Field | Value |
|-------|-------|
| `data_hash` | `2db51323838d0dbe39b960b92cfdb6cb1f3a2e5a4477f3336fa15f3c9af8b79d` — SHA-256 of holdout.parquet |
| `source_dataset` | `laramee26openBankTransactionData.xlsx` |
| `scope` | **UK / GBP-scoped** open banking transactions. Merchant names, transaction-type codes (DEB/BP/DD/CPT/…) and amounts are British. A US/other-locale deployment will need re-training on local data. |
| `input_text` | `Transaction Description` + the bracketed `Transaction Type` code, e.g. `LIDL GB NOTTINGHA [DEB]`. |

The holdout hash must equal `split_manifest.hashes.holdout`. It is the only accepted
proof that the gate runs on the exact slice the model never trained on.

### Dataset quirks & cleaning (see docs/DECISIONS.md, 2026-06-16)

- **`amazon` is its own category** — a dataset artifact. The source labels ~1,195 rows
  (the single largest class after down-sampling) as the native category "Amazon"
  rather than splitting them into shopping/groceries/etc. We preserve it as a label
  because the description text (`Amazon.co.uk*…`) is unambiguous and re-bucketing would
  be guesswork. Consumers should treat `amazon` as "an Amazon purchase, sub-category
  unknown."
- **`SAVE THE CHANGE` down-sampled** 1,165 → 150. It is one identical string repeated;
  left intact it inflates the `savings` class and overall accuracy.
- **24 null-Category rows dropped.** (Note: an earlier research pass cited "1,771 (21%)"
  nulls — that was a differently-sized copy of the file; this 6,567-row copy has 24.)
- **Singletons dropped**: Rent, Health, Account transfer, Purchase of uk.eg.org,
  Safety Deposit Return, Travel Reimbursement.
- **Merges**: Food Shopping→groceries; Paycheck+Supplementary Income→income;
  Investment+Interest→investment; Home Improvement+Services/Home Improvement→home_improvement.

## Metrics (Phase 2 — baseline is champion)

| Model | Val macro-F1 | Holdout macro-F1 | Latency (ms) | Cost/call |
|-------|-------------|------------------|--------------|-----------|
| TF-IDF+LR baseline (champion) | 0.8361 | **0.8934** | ~10 | ~$0 |
| Gemini zero-shot | run on sample only | N/A | — | per-call LLM cost |
| DistilBERT fine-tune (3-epoch CPU) | — | 0.8677 | — | ~$0 |

**Winner: TF-IDF+LR.** A local 3-epoch CPU DistilBERT fine-tune scored 0.8677 holdout —
below the baseline's 0.8934 — so the classical model ships as champion (the gate's
beat-baseline rule blocks promoting a weaker model). On short, high-signal merchant
strings, n-gram TF-IDF captures the discriminative tokens directly; a longer Colab GPU
run (5 epochs, the notebook's recipe) may narrow the gap but did not run here.

Per-class holdout F1 is strong for the well-populated classes (bills/cash/investment/
mortgage = 1.0; amazon/savings/groceries > 0.95). The thin classes (fitness, clothes,
hotels, …) score low and are governed by the **always_review** rule, not the gate's
per-class F1 floor.

## Freeze policy

- **Foundation model (this phase)**: full fine-tune (DistilBERT, when run) / full fit
  (classical baseline) on the training split.
- **In-stack retrains (Phase 5)**: partial unfreeze — top N transformer layers only.
  The retrain never sees the frozen holdout; it uses human-confirmed corrections only.

## Gate floor

`macro_f1_min` = 0.84 (holdout 0.8934 − 0.05 tolerance).
See `eval_thresholds.yaml` and `docs/DECISIONS.md` for rationale.
