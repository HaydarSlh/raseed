"""T025 — TF-IDF + Logistic Regression baseline (US3).

Trains a classical TF-IDF + LR pipeline on the training split, evaluates on val
and the holdout, calibrates confidence (isotonic regression), and exports to ONNX
via skl2onnx. This is the always-present comparison model for the CI gate.

Usage:
    python training/train_baseline.py [--data-dir training/data]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "training" / "data"
TAXONOMY_PATH = REPO_ROOT / "training" / "taxonomy.yaml"
OUTPUT_DIR = DATA_DIR  # baseline.onnx written here


def _load_split(data_dir: Path, name: str) -> pd.DataFrame:
    return pd.read_parquet(data_dir / f"{name}.parquet")


def train(data_dir: Path = DATA_DIR) -> dict:
    with (REPO_ROOT / "training" / "taxonomy.yaml").open() as f:
        taxonomy = yaml.safe_load(f)
    categories: list[str] = taxonomy["categories"]

    train_df = _load_split(data_dir, "train")
    val_df = _load_split(data_dir, "val")
    holdout_df = pd.read_parquet(data_dir / "holdout.parquet")

    print(f"Train: {len(train_df):,}  Val: {len(val_df):,}  Holdout: {len(holdout_df):,}")

    # TF-IDF + LR pipeline — train on full train split for ONNX export.
    base_pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=50_000, sublinear_tf=True)),
        ("lr", LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced", solver="saga")),
    ])

    print("Training calibrated TF-IDF + LR...")
    t_start = time.perf_counter()
    base_pipeline.fit(train_df["description"].tolist(), train_df["category"].tolist())
    # Calibrate with cv="prefit" so the fitted pipeline is reused (no re-training).
    calibrated = CalibratedClassifierCV(base_pipeline, method="isotonic", cv="prefit")
    calibrated.fit(val_df["description"].tolist(), val_df["category"].tolist())
    train_time_s = time.perf_counter() - t_start
    print(f"Training done in {train_time_s:.1f}s")

    # Evaluate on val (using raw pipeline — calibrator was trained on val so val metrics would be inflated).
    val_preds = base_pipeline.predict(val_df["description"].tolist())
    val_macro = f1_score(
        val_df["category"], val_preds, labels=categories, average="macro", zero_division=0
    )
    val_per_class = f1_score(
        val_df["category"], val_preds, labels=categories, average=None, zero_division=0
    )
    print(f"Val macro-F1:  {val_macro:.4f}")

    # Evaluate on holdout.
    holdout_preds = base_pipeline.predict(holdout_df["description"].tolist())
    holdout_macro = f1_score(
        holdout_df["category"], holdout_preds, labels=categories, average="macro", zero_division=0
    )
    print(f"Holdout macro-F1: {holdout_macro:.4f}")

    # Single-call latency (cost ≈ 0).
    _ = calibrated.predict_proba(["warmup"])
    t0 = time.perf_counter()
    calibrated.predict_proba(["STARBUCKS COFFEE STORE"])
    latency_ms = (time.perf_counter() - t0) * 1000
    print(f"Single-call latency: {latency_ms:.2f} ms")

    # Export to ONNX via skl2onnx — export the base_pipeline (string in, proba out).
    # CalibratedClassifierCV cannot be directly exported since skl2onnx requires numeric
    # inputs for calibrators; base_pipeline (TF-IDF + LR) handles string→proba natively.
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import StringTensorType

        initial_type = [("string_input", StringTensorType([None, 1]))]
        onnx_model = convert_sklearn(base_pipeline, initial_types=initial_type)
        baseline_path = data_dir / "baseline.onnx"
        with baseline_path.open("wb") as f:
            f.write(onnx_model.SerializeToString())
        print(f"Baseline ONNX written to {baseline_path}")

        # Smoke-test the ONNX export.
        sess = ort.InferenceSession(str(baseline_path), providers=["CPUExecutionProvider"])
        out = sess.run(None, {"string_input": np.array([["GROCERY STORE VISIT"]])})
        print(f"ONNX smoke-test output: {out[0]}")

    except ImportError:
        print("skl2onnx not found — skipping ONNX export (install training requirements).")
        baseline_path = None

    # Save holdout predictions for the gate.
    holdout_pred_path = data_dir / "baseline_holdout_preds.parquet"
    pd.DataFrame({"category": holdout_preds}).to_parquet(holdout_pred_path)
    print(f"Holdout predictions written to {holdout_pred_path}")

    results = {
        "model": "tf-idf+lr (calibrated)",
        "val_macro_f1": round(val_macro, 4),
        "holdout_macro_f1": round(holdout_macro, 4),
        "per_class_f1": {
            cat: round(float(sc), 4)
            for cat, sc in zip(categories, val_per_class)
        },
        "latency_ms": round(latency_ms, 2),
        "cost_per_call": 0.0,
        "baseline_onnx": str(baseline_path) if baseline_path else None,
        "holdout_preds": str(holdout_pred_path),
    }

    results_path = data_dir / "baseline_results.json"
    with results_path.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"Results written to {results_path}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Train TF-IDF + LR baseline.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    results = train(data_dir=args.data_dir)
    print(f"\nSummary: val_macro_f1={results['val_macro_f1']} holdout={results['holdout_macro_f1']}")


if __name__ == "__main__":
    main()
