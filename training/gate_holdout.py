"""CI gate #1 — categorizer quality gate (US2, T022).

Loads champion + classical-baseline predictions on the frozen holdout and asserts:
  PASS iff:
    C − B >= beat_baseline_margin      (always-binding; C = champion macro-F1)
    C >= macro_f1_min                  (ratcheting absolute floor)
    min(per_class_F1(C)) >= min_per_class_f1
    single_call_latency_ms <= max_inference_latency_ms

Exits 0 on PASS, non-zero on FAIL.

NOTE: max_inference_latency_ms is a SINGLE-CALL bound.
The p95 measurement of record lives in T033 (quickstart/latency benchmark).

Stack-independent: reads only committed LFS artifacts (holdout.parquet, ONNX files,
eval_thresholds.yaml). Never imports compose services or starts any server.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import f1_score


# ── Public API (also called directly by test_gate.py) ────────────────────────

def gate(
    holdout_path: Path,
    champion_pred_path: Path,
    baseline_pred_path: Path,
    thresholds_path: Path,
    taxonomy_path: Path | None,
    latency_ms: float,
) -> int:
    """Run the gate. Returns 0 on PASS, 1 on FAIL."""
    thresholds = _load_thresholds(thresholds_path)

    holdout = pd.read_parquet(holdout_path)
    true_labels = holdout["category"].tolist()

    champion_preds = pd.read_parquet(champion_pred_path)["category"].tolist()
    baseline_preds = pd.read_parquet(baseline_pred_path)["category"].tolist()

    categories = sorted(set(true_labels))
    champion_macro = _macro_f1(true_labels, champion_preds, categories)
    baseline_macro = _macro_f1(true_labels, baseline_preds, categories)
    champion_per_class_f1 = _per_class_f1(true_labels, champion_preds, categories)
    min_class_f1 = float(min(champion_per_class_f1.values(), default=0.0))

    margin = thresholds["beat_baseline_margin"]
    floor = thresholds["macro_f1_min"]
    min_class = thresholds["min_per_class_f1"]
    max_lat = thresholds["max_inference_latency_ms"]

    print(f"Champion macro-F1:     {champion_macro:.4f}")
    print(f"Baseline macro-F1:     {baseline_macro:.4f}")
    print(f"Margin (C-B):          {champion_macro - baseline_macro:.4f} (required >= {margin})")
    print(f"Floor check:           {champion_macro:.4f} (required >= {floor})")
    print(f"Min per-class F1:      {min_class_f1:.4f} (required >= {min_class})")
    print(f"Single-call latency:   {latency_ms:.1f} ms (limit {max_lat} ms)")

    failures: list[str] = []
    if champion_macro - baseline_macro < margin:
        failures.append(
            f"champion does not beat baseline by required margin "
            f"({champion_macro:.4f} − {baseline_macro:.4f} = "
            f"{champion_macro - baseline_macro:.4f} < {margin})"
        )
    if champion_macro < floor:
        failures.append(f"champion macro-F1 {champion_macro:.4f} below floor {floor}")
    if min_class_f1 < min_class:
        failures.append(f"min per-class F1 {min_class_f1:.4f} below {min_class}")
    if latency_ms > max_lat:
        failures.append(f"latency {latency_ms:.1f} ms exceeds limit {max_lat} ms")

    if failures:
        print("\nFAIL GATE FAILED:")
        for f in failures:
            print(f"  -{f}")
        return 1

    print("\nPASS GATE PASSED")
    return 0


# ── Metrics helpers ───────────────────────────────────────────────────────────

def _macro_f1(true: list[str], pred: list[str], labels: list[str]) -> float:
    return float(f1_score(true, pred, labels=labels, average="macro", zero_division=0))


def _per_class_f1(true: list[str], pred: list[str], labels: list[str]) -> dict[str, float]:
    scores = f1_score(true, pred, labels=labels, average=None, zero_division=0)
    return {lab: float(sc) for lab, sc in zip(labels, scores)}


def _load_thresholds(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = yaml.safe_load(f)
    block = (data or {}).get("categorizer") or {}
    required = ["beat_baseline_margin", "macro_f1_min", "min_per_class_f1", "max_inference_latency_ms"]
    missing = [k for k in required if block.get(k) is None]
    if missing:
        print(f"FAIL eval_thresholds.yaml categorizer block missing/null: {missing}")
        sys.exit(1)
    return {k: block[k] for k in required}


# ── Standalone CLI ────────────────────────────────────────────────────────────

def _measure_single_call_latency(onnx_path: Path, tokenizer_path: Path | None) -> float:
    """Measure a single-call inference latency (ms)."""
    import time
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    session = ort.InferenceSession(str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"])
    first_input = session.get_inputs()[0]

    if "string" in first_input.type:
        feeds = {first_input.name: np.array([["grocery store visit"]])}
    else:
        if tokenizer_path and tokenizer_path.exists():
            from tokenizers import Tokenizer
            tok = Tokenizer.from_file(str(tokenizer_path))
            tok.enable_truncation(max_length=128)
            tok.enable_padding(pad_id=0, pad_token="[PAD]", length=128)
            enc = tok.encode("grocery store visit")
            feeds = {
                "input_ids": np.array([enc.ids], dtype=np.int64),
                "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
            }
        else:
            feeds = {
                "input_ids": np.zeros((1, 128), dtype=np.int64),
                "attention_mask": np.ones((1, 128), dtype=np.int64),
            }

    # Warm up
    session.run(None, feeds)
    # Measure
    t0 = time.perf_counter()
    session.run(None, feeds)
    return (time.perf_counter() - t0) * 1000


def _generate_predictions(onnx_path: Path, tokenizer_path: Path | None, holdout: pd.DataFrame) -> list[str]:
    """Run the model over all holdout descriptions to generate predictions."""
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    session = ort.InferenceSession(str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"])
    first_input = session.get_inputs()[0]
    preds: list[str] = []

    categories: list[str] = []
    # Try to get category list from model metadata or output shape
    # Fall back to unique labels in holdout
    categories = sorted(holdout["category"].unique().tolist())

    if "string" in first_input.type:
        for desc in holdout["description"]:
            out = session.run(None, {first_input.name: np.array([[desc]])})
            # skl2onnx: output[0] is label, output[1] is proba
            label = out[0][0] if isinstance(out[0][0], str) else categories[int(np.argmax(out[-1][0]))]
            preds.append(str(label))
    else:
        if tokenizer_path and tokenizer_path.exists():
            from tokenizers import Tokenizer
            tok = Tokenizer.from_file(str(tokenizer_path))
            tok.enable_truncation(max_length=128)
            tok.enable_padding(pad_id=0, pad_token="[PAD]", length=128)
        else:
            tok = None

        for desc in holdout["description"]:
            if tok:
                enc = tok.encode(str(desc))
                feeds = {
                    "input_ids": np.array([enc.ids], dtype=np.int64),
                    "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
                }
            else:
                feeds = {
                    "input_ids": np.zeros((1, 128), dtype=np.int64),
                    "attention_mask": np.ones((1, 128), dtype=np.int64),
                }
            out = session.run(None, feeds)
            logits = out[0][0]
            preds.append(categories[int(np.argmax(logits))])

    return preds


def main() -> None:
    repo_root = Path(__file__).parent.parent

    parser = argparse.ArgumentParser(description="Categorizer CI gate #1.")
    parser.add_argument(
        "--holdout",
        type=Path,
        default=repo_root / "training" / "data" / "holdout.parquet",
    )
    parser.add_argument(
        "--champion",
        type=Path,
        default=repo_root / "modelserver" / "artifacts" / "categorizer.onnx",
        help="Champion ONNX model path.",
    )
    parser.add_argument(
        "--champion-tokenizer",
        type=Path,
        default=repo_root / "modelserver" / "artifacts" / "tokenizer.json",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=repo_root / "training" / "data" / "baseline.onnx",
        help="Classical baseline ONNX model path.",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=repo_root / "eval_thresholds.yaml",
    )
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=repo_root / "training" / "taxonomy.yaml",
    )
    args = parser.parse_args()

    holdout = pd.read_parquet(args.holdout)
    print(f"Holdout: {len(holdout)} rows")

    print("Generating champion predictions...")
    champion_tok = args.champion_tokenizer if args.champion_tokenizer.exists() else None
    champion_preds = _generate_predictions(args.champion, champion_tok, holdout)

    print("Generating baseline predictions...")
    baseline_preds = _generate_predictions(args.baseline, None, holdout)

    # Write tmp prediction files for the gate function
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        champ_pred_path = tmp / "champion_preds.parquet"
        base_pred_path = tmp / "baseline_preds.parquet"
        pd.DataFrame({"category": champion_preds}).to_parquet(champ_pred_path)
        pd.DataFrame({"category": baseline_preds}).to_parquet(base_pred_path)

        latency = _measure_single_call_latency(args.champion, champion_tok)
        print(f"Single-call latency: {latency:.1f} ms")

        code = gate(
            holdout_path=args.holdout,
            champion_pred_path=champ_pred_path,
            baseline_pred_path=base_pred_path,
            thresholds_path=args.thresholds,
            taxonomy_path=args.taxonomy,
            latency_ms=latency,
        )

    sys.exit(code)


if __name__ == "__main__":
    main()
