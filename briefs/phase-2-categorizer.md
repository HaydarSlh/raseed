# Phase 2 — Categorizer: trained offline (Colab GPU), served lean

## Intent
A transaction description goes in; a category + calibrated confidence comes out,
from a model fine-tuned by the developer, behind a lean in-stack service.

## In scope (deliverables)
- Dataset preparation from the Kaggle USA Banking Transactions set; locked
  category taxonomy; stratified train/val/test split with fixed seeds; the
  frozen holdout committed (Git LFS) — touched only by the champion gate.
- Offline training IN COLAB ON GPU (`training/notebooks/`): TF-IDF + logistic
  regression baseline, fine-tuned DistilBERT, Gemini zero-shot baseline —
  macro-F1, per-class F1 (categories are imbalanced), latency, cost per call.
  Three numbers recorded in DECISIONS.md; the winner ships.
- ONNX export (`training/export_onnx.py`), model card with data hash, metrics,
  freeze policy, and pinned artifact SHA-256.
- Lean model-server (onnxruntime + numpy): /predict returning category +
  confidence (+ top-k alternatives), /healthz; STRICT refuse-to-boot on missing
  artifact or hash mismatch activates now.
- Operating threshold chosen by an explicit rule (e.g. highest threshold holding
  >=97% precision on validation) and committed to eval_thresholds.yaml.
- CI gate #1: macro-F1 >= threshold on the frozen holdout AND beats the
  classical baseline. Artifact + holdout reach CI via Git LFS (or a release
  asset) — never fetched from the running stack.

## Out of scope
The ingestion pipeline (Phase 3); automated retraining (Phase 5).

## Acceptance criteria
- Model-server answers over HTTP inside compose; image lean (no torch).
- Gate #1 green in CI with real numbers; DECISIONS.md records the three-way
  comparison and the threshold rule.

## Notes for /plan
torch exists only in Colab and (later) the trainer image. The model card's
freeze policy section must state: full fine-tune for the foundation model,
partial unfreeze for in-stack retrains (Phase 5).
