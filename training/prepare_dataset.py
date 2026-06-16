"""Prepare the open bank transaction dataset for training (data cleaning deliverable).

Reads raw data from training/data/raw/ (developer-provided, never committed).
Source: laramee26openBankTransactionData.xlsx (UK / GBP open banking transactions).

Cleaning steps (all recorded in docs/DECISIONS.md, 2026-06-16):
  1. Drop rows with null Category.
  2. Strip whitespace on Category; apply the consolidation map from taxonomy.yaml.
  3. Singleton/near-singleton categories fall through to `other` and are dropped.
  4. Down-sample the "SAVE THE CHANGE" rows (Savings) so one class can't dominate.
  5. Input text = Transaction Description (+ Transaction Type code when present);
     target = cleaned Category.

Produces:
  - training/data/{train,val,test}.parquet
  - training/data/holdout.parquet      — frozen holdout (Git LFS, gate-only)
  - training/data/split_manifest.json  — seeds, per-class counts, content hashes

Usage:
    python training/prepare_dataset.py [--raw-dir training/data/raw]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml
from sklearn.model_selection import train_test_split

# ── Seeds (fixed — never change; bump taxonomy.yaml version if re-split needed) ──
SEED_SPLIT = 42
SEED_SHUFFLE = 7

# ── Split fractions (train : val : test : holdout) ──
# 70 / 10 / 10 / 10  (holdout carved last, never touched after this script)
VAL_SIZE = 0.10
TEST_SIZE = 0.10
HOLDOUT_SIZE = 0.10

# ── Down-sampling: "SAVE THE CHANGE" is an identical string repeated ~1165× and
# would inflate the Savings class. Cap it so Savings sits mid-pack with the other
# major classes (see docs/DECISIONS.md). Random subset, fixed seed for reproducibility.
SAVE_THE_CHANGE_TEXT = "SAVE THE CHANGE"
SAVE_THE_CHANGE_CAP = 150

# ── Paths ──
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "training" / "data"
RAW_DIR = DATA_DIR / "raw"
TAXONOMY_PATH = REPO_ROOT / "training" / "taxonomy.yaml"

# ── Column names in the laramee open bank transaction dataset ──
DESC_COL = "Transaction Description"
TYPE_COL = "Transaction Type"
CAT_COL = "Category"


def _content_hash(df: pd.DataFrame) -> str:
    """Deterministic SHA-256 of a DataFrame's canonical CSV representation."""
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def _source_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_raw_file(raw_dir: Path) -> Path:
    """Return the primary raw dataset (prefer .xlsx, then .csv)."""
    for pattern in ("*.xlsx", "*.csv"):
        matches = sorted(raw_dir.glob(pattern))
        if matches:
            if len(matches) > 1:
                print(f"Multiple {pattern} found in {raw_dir}; using {matches[0].name}")
            return matches[0]
    raise FileNotFoundError(
        f"No .xlsx or .csv found in {raw_dir}. "
        "Drop the dataset there or see training/README.md."
    )


def _read_raw(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path, low_memory=False)


def _build_input_text(df: pd.DataFrame) -> pd.Series:
    """Input text = Transaction Description, optionally suffixed with the type code.

    The type code (DEB, BP, DD, CPT, FPO, ...) is a weak but real signal (e.g. DD =
    direct debit ≈ bills/insurance; FPI/BGC ≈ income). We append it as a token so the
    model can use it without it dominating the description.
    """
    desc = df[DESC_COL].astype(str).str.strip()
    if TYPE_COL in df.columns:
        ttype = df[TYPE_COL].astype(str).str.strip()
        # Skip obvious nulls rendered as text.
        ttype = ttype.where(~ttype.str.lower().isin(["nan", "none", ""]), "")
        text = desc.where(ttype == "", desc + " [" + ttype + "]")
        return text
    return desc


def load_and_clean(raw_path: Path, taxonomy: dict) -> tuple[pd.DataFrame, dict]:
    """Load raw dataset, clean, apply taxonomy, down-sample. Returns (df, cleaning_stats)."""
    raw = _read_raw(raw_path)
    n_raw = len(raw)

    consolidation = {k.strip(): v for k, v in taxonomy["consolidation_map"].items()}
    valid_categories = set(taxonomy["categories"])

    # 1. Drop null Category.
    n_null_cat = int(raw[CAT_COL].isna().sum())
    df = raw[raw[CAT_COL].notna()].copy()

    # 2. Build input text + clean category.
    df["description"] = _build_input_text(df)
    df["raw_category"] = df[CAT_COL].astype(str).str.strip()
    df = df[df["description"].str.len() > 0]

    # 3. Apply consolidation map; "Others" + unmapped/singletons → `other` sentinel.
    df["category"] = df["raw_category"].map(consolidation).fillna("other")

    # Track which raw categories were dropped (unmapped singletons; "Others" is mapped).
    all_raw_cats = set(raw[CAT_COL].dropna().astype(str).str.strip().unique())
    dropped_raw = sorted(all_raw_cats - set(consolidation.keys()))

    # 4. Drop the `other` sentinel — not a model label (see taxonomy.yaml).
    n_other = int((df["category"] == "other").sum())
    df = df[df["category"].isin(valid_categories)]
    n_after_map = len(df)

    # 5. Down-sample "SAVE THE CHANGE" so Savings doesn't dominate.
    is_stc = df["description"].str.upper().str.startswith(SAVE_THE_CHANGE_TEXT)
    n_stc = int(is_stc.sum())
    if n_stc > SAVE_THE_CHANGE_CAP:
        stc_keep = df[is_stc].sample(n=SAVE_THE_CHANGE_CAP, random_state=SEED_SHUFFLE)
        df = pd.concat([df[~is_stc], stc_keep], ignore_index=True)
    n_stc_kept = min(n_stc, SAVE_THE_CHANGE_CAP)

    df = df[["description", "category"]].reset_index(drop=True)

    stats = {
        "n_raw": n_raw,
        "n_null_category_dropped": n_null_cat,
        "n_after_consolidation": n_after_map,
        "n_other_dropped": n_other,
        "save_the_change_total": n_stc,
        "save_the_change_kept": n_stc_kept,
        "dropped_raw_categories": [c for c in dropped_raw if c != "Others"],
        "n_final": len(df),
    }
    return df, stats


def stratified_split(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fixed-seed stratified split → (train, val, test, holdout)."""
    # Carve holdout first so it is never contaminated by hyper-param search.
    rest, holdout = train_test_split(
        df, test_size=HOLDOUT_SIZE, stratify=df["category"], random_state=SEED_SPLIT
    )
    remaining_val_test = VAL_SIZE + TEST_SIZE
    train, val_test = train_test_split(
        rest,
        test_size=remaining_val_test / (1 - HOLDOUT_SIZE),
        stratify=rest["category"],
        random_state=SEED_SPLIT,
    )
    val, test = train_test_split(
        val_test,
        test_size=TEST_SIZE / remaining_val_test,
        stratify=val_test["category"],
        random_state=SEED_SPLIT,
    )
    return (
        train.reset_index(drop=True),
        val.reset_index(drop=True),
        test.reset_index(drop=True),
        holdout.reset_index(drop=True),
    )


def per_class_counts(df: pd.DataFrame) -> dict[str, int]:
    return {k: int(v) for k, v in df["category"].value_counts().to_dict().items()}


def main(raw_dir: Path = RAW_DIR) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    with TAXONOMY_PATH.open(encoding="utf-8") as f:
        taxonomy = yaml.safe_load(f)

    raw_path = _find_raw_file(raw_dir)
    print(f"Loading {raw_path.name} ...")
    df, stats = load_and_clean(raw_path, taxonomy)

    print("\n=== Cleaning report ===")
    print(f"  Raw rows:                  {stats['n_raw']:,}")
    print(f"  Dropped (null Category):   {stats['n_null_category_dropped']:,}")
    print(f"  After consolidation map:   {stats['n_after_consolidation']:,}")
    print(f"  Dropped ('other'/Others):  {stats['n_other_dropped']:,}")
    print(f"  Dropped singleton cats:    {stats['dropped_raw_categories']}")
    print(
        f"  SAVE THE CHANGE down-sample: {stats['save_the_change_total']:,} "
        f"-> {stats['save_the_change_kept']:,}"
    )
    print(f"  Final training rows:       {stats['n_final']:,}")

    print("\n=== Per-class counts (final, pre-split) ===")
    full_counts = per_class_counts(df)
    for cat, n in sorted(full_counts.items(), key=lambda kv: -kv[1]):
        flag = "  <-- thin (N<20 -> always_review likely)" if n < 30 else ""
        print(f"  {cat:18s} {n:5d}{flag}")

    train, val, test, holdout = stratified_split(df)
    print(
        f"\nSplit: train={len(train):,} val={len(val):,} "
        f"test={len(test):,} holdout={len(holdout):,}"
    )

    for name, split_df in [("train", train), ("val", val), ("test", test)]:
        split_df.to_parquet(DATA_DIR / f"{name}.parquet", index=False)

    holdout_path = DATA_DIR / "holdout.parquet"
    holdout.to_parquet(holdout_path, index=False)
    print(f"Holdout written to {holdout_path} (frozen - gate-only).")

    manifest = {
        "seeds": {"split": SEED_SPLIT, "shuffle": SEED_SHUFFLE},
        "cleaning": stats,
        "counts": {
            "train": per_class_counts(train),
            "val": per_class_counts(val),
            "test": per_class_counts(test),
            "holdout": per_class_counts(holdout),
        },
        "hashes": {
            "train": _content_hash(train),
            "val": _content_hash(val),
            "test": _content_hash(test),
            "holdout": _content_hash(holdout),
        },
        "taxonomy_version": taxonomy["version"],
        "source_dataset": {
            "name": raw_path.name,
            "source_hash": _source_hash(raw_path),
            "scope": "UK / GBP open banking transactions",
        },
    }
    manifest_path = DATA_DIR / "split_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {manifest_path}.")
    print(f"Holdout hash: {manifest['hashes']['holdout']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare training dataset.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_DIR,
        help="Path to directory containing the raw dataset (.xlsx/.csv).",
    )
    args = parser.parse_args()
    main(raw_dir=args.raw_dir)
