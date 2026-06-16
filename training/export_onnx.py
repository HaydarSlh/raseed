"""T028 — Export winner to ONNX with per-category operating thresholds (US3).

Takes the winner (DistilBERT champion or classical baseline) and produces:
  - modelserver/artifacts/categorizer.onnx
  - modelserver/artifacts/tokenizer.json  (neural champion only)
  - training/data/operating_thresholds.json
  - Prints: SHA-256 of categorizer.onnx (pin in config.py, T030)

Per-category operating threshold rule:
  highest confidence cut holding >=97% precision on the validation set.
  A category with < 20 validation samples -> "always_review" sentinel (N=20 rule).
  (See DECISIONS.md 2026-06-15, FR-009, U1 remediation.)

Usage (after Colab champion):
    python training/export_onnx.py --mode champion \
        --model training/data/champion.onnx \
        --tokenizer training/data/champion_tokenizer.json

Usage (baseline only, before Colab run):
    python training/export_onnx.py --mode baseline
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "training" / "data"
ARTIFACTS_DIR = REPO_ROOT / "modelserver" / "artifacts"
TAXONOMY_PATH = REPO_ROOT / "training" / "taxonomy.yaml"
THRESHOLDS_PATH = REPO_ROOT / "eval_thresholds.yaml"

SPARSE_CLASS_N = 20  # N=20 rule (DECISIONS.md 2026-06-15, FR-009)
MIN_PRECISION = 0.97  # operating threshold targets >=97% precision


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_taxonomy() -> list[str]:
    with TAXONOMY_PATH.open() as f:
        return list(yaml.safe_load(f)["categories"])


def _load_val(data_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(data_dir / "val.parquet")


def _run_model_on_val(
    onnx_path: Path,
    tokenizer_path: Path | None,
    val_df: pd.DataFrame,
) -> tuple[list[str], np.ndarray]:
    """Return (predicted_labels, confidence_matrix [N, num_cats])."""
    import onnxruntime as ort

    categories = _load_taxonomy()
    so = ort.SessionOptions()
    so.log_severity_level = 3
    session = ort.InferenceSession(str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"])
    first_input = session.get_inputs()[0]

    preds: list[str] = []
    probs_list: list[np.ndarray] = []

    def softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - x.max())
        return e / e.sum()

    if "string" in first_input.type:
        for desc in val_df["description"]:
            out = session.run(None, {first_input.name: np.array([[str(desc)]])})
            label_out = out[0][0]
            if isinstance(label_out, bytes):
                label_out = label_out.decode()
            preds.append(str(label_out))
            # second output is probability map or array
            if len(out) > 1:
                proba = out[1]
                if isinstance(proba, list):
                    # dict output from skl2onnx
                    proba_vec = np.array([proba[0].get(c, 0.0) for c in categories])
                else:
                    proba_vec = np.array(proba[0])
            else:
                proba_vec = np.zeros(len(categories))
                if label_out in categories:
                    proba_vec[categories.index(label_out)] = 1.0
            probs_list.append(proba_vec)
    else:
        if tokenizer_path and tokenizer_path.exists():
            from tokenizers import Tokenizer
            tok = Tokenizer.from_file(str(tokenizer_path))
            tok.enable_truncation(max_length=128)
            tok.enable_padding(pad_id=0, pad_token="[PAD]", length=128)
        else:
            tok = None

        for desc in val_df["description"]:
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
            proba = softmax(logits)
            preds.append(categories[int(np.argmax(proba))])
            probs_list.append(proba)

    return preds, np.array(probs_list)


def compute_operating_thresholds(
    true_labels: list[str],
    pred_labels: list[str],
    confidences: np.ndarray,
    categories: list[str],
) -> dict[str, Any]:
    """Per-category: highest cut holding >=97% precision. N<20 -> always_review."""
    thresholds: dict[str, Any] = {}
    cat_to_idx = {c: i for i, c in enumerate(categories)}

    for cat in categories:
        cat_true = [tl == cat for tl in true_labels]
        n_val = sum(cat_true)

        if n_val < SPARSE_CLASS_N:
            thresholds[cat] = "always_review"
            print(f"  {cat}: {n_val} val samples < {SPARSE_CLASS_N} -> always_review")
            continue

        cat_idx = cat_to_idx.get(cat)
        if cat_idx is None:
            thresholds[cat] = "always_review"
            continue

        cat_conf = confidences[:, cat_idx]

        # Sweep thresholds from 0.0 to 1.0 in 0.01 steps.
        best_threshold = 0.0
        best_precision = 0.0
        for t in np.arange(0.01, 1.01, 0.01):
            above_thresh = [(p == cat and c >= t) for p, c in zip(pred_labels, cat_conf)]
            n_above = sum(above_thresh)
            if n_above == 0:
                break
            true_positive = sum(
                a and true for a, true in zip(above_thresh, cat_true)
            )
            precision = true_positive / n_above
            if precision >= MIN_PRECISION:
                best_threshold = float(t)
                best_precision = precision

        if best_threshold > 0:
            thresholds[cat] = round(best_threshold, 2)
            print(f"  {cat}: threshold={best_threshold:.2f} (precision={best_precision:.3f})")
        else:
            thresholds[cat] = "always_review"
            print(f"  {cat}: no threshold holds >={MIN_PRECISION:.0%} precision -> always_review")

    return thresholds


def main() -> None:
    parser = argparse.ArgumentParser(description="Export winner to ONNX + thresholds.")
    parser.add_argument(
        "--mode",
        choices=["champion", "baseline"],
        default="baseline",
        help="'champion' uses the Colab-produced DistilBERT; 'baseline' uses the LR baseline.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Path to winner ONNX (champion mode; defaults to training/data/champion.onnx).",
    )
    parser.add_argument(
        "--tokenizer",
        type=Path,
        default=None,
        help="Path to tokenizer.json (champion mode only).",
    )
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()

    categories = _load_taxonomy()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode == "champion":
        model_path = args.model or (args.data_dir / "champion.onnx")
        tokenizer_path = args.tokenizer or (args.data_dir / "champion_tokenizer.json")
    else:
        model_path = args.data_dir / "baseline.onnx"
        tokenizer_path = None

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}\n"
            "Run train_baseline.py (or Colab for champion) first."
        )

    print(f"Exporting {model_path} -> {ARTIFACTS_DIR}/categorizer.onnx")
    dest_onnx = ARTIFACTS_DIR / "categorizer.onnx"
    shutil.copy2(model_path, dest_onnx)

    if tokenizer_path and tokenizer_path.exists():
        dest_tok = ARTIFACTS_DIR / "tokenizer.json"
        shutil.copy2(tokenizer_path, dest_tok)
        print(f"Copied tokenizer -> {dest_tok}")
    else:
        print("No tokenizer (classical model or tokenizer not provided).")

    artifact_sha = sha256_of(dest_onnx)
    print(f"\nArtifact SHA-256: {artifact_sha}")
    print("-> Pin this in modelserver/config.py as MODELSERVER_EXPECTED_SHA256 (T030)")

    # Compute per-category operating thresholds on validation set.
    print("\nComputing per-category operating thresholds on val set…")
    val_df = _load_val(args.data_dir)
    val_tok = tokenizer_path if (tokenizer_path and tokenizer_path.exists()) else None
    pred_labels, conf_matrix = _run_model_on_val(dest_onnx, val_tok, val_df)
    true_labels = val_df["category"].tolist()

    print(f"  Sparse-class rule: N < {SPARSE_CLASS_N} validation samples -> always_review")
    op_thresholds = compute_operating_thresholds(true_labels, pred_labels, conf_matrix, categories)

    thresholds_out = args.data_dir / "operating_thresholds.json"
    with thresholds_out.open("w") as f:
        json.dump(op_thresholds, f, indent=2)
    print(f"\nOperating thresholds written to {thresholds_out}")
    print("-> Copy these into eval_thresholds.yaml categorizer.operating_thresholds (T031)")

    # Produce holdout predictions for the gate.
    print("\nGenerating champion holdout predictions for the gate…")
    holdout_df = pd.read_parquet(args.data_dir / "holdout.parquet")
    champion_holdout_preds, _ = _run_model_on_val(dest_onnx, val_tok, holdout_df)
    holdout_pred_path = args.data_dir / "champion_holdout_preds.parquet"
    pd.DataFrame({"category": champion_holdout_preds}).to_parquet(holdout_pred_path)

    from sklearn.metrics import f1_score
    holdout_macro = float(f1_score(
        holdout_df["category"], champion_holdout_preds,
        labels=categories, average="macro", zero_division=0,
    ))
    print(f"Champion holdout macro-F1: {holdout_macro:.4f}")
    print(f"Holdout preds: {holdout_pred_path}")
    print("\nNext: fill eval_thresholds.yaml (T031) and commit the artifact (T030).")


if __name__ == "__main__":
    main()
