"""T009 — Deterministic split test (SC-009).

Re-runs prepare_dataset logic with fixed seeds and asserts that per-split content
hashes are identical across two runs. Also asserts holdout hash stability.

These tests run on a tiny synthetic dataset (no raw data needed) to stay
fast and data-independent.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.prepare_dataset import (
    _content_hash,
    load_and_clean,
    stratified_split,
)

# `other` is intentionally NOT in categories — it is the drop sentinel (matches the
# real taxonomy.yaml v2.0.0 design). "Others"/unmapped rows map to it and get dropped.
TAXONOMY = {
    "version": "2.0.0",
    "categories": [
        "groceries", "dining", "transport", "utilities", "healthcare",
        "entertainment", "shopping", "travel", "education", "income",
        "transfer", "fees",
    ],
    "consolidation_map": {
        "Grocery": "groceries",
        "Restaurant": "dining",
        "Gas & Fuel": "transport",
        "Utilities": "utilities",
        "Health & Fitness": "healthcare",
        "Entertainment": "entertainment",
        "Shopping": "shopping",
        "Travel": "travel",
        "Education": "education",
        "Paycheck": "income",
        "Transfer": "transfer",
        "ATM Fee": "fees",
        "Misc Expenses": "other",
    },
}


def _make_synthetic_df(n_per_class: int = 40) -> pd.DataFrame:
    """Build a synthetic DataFrame with the full taxonomy, n rows per class."""
    rows = []
    for cat in TAXONOMY["categories"]:
        for i in range(n_per_class):
            rows.append({"description": f"{cat} transaction {i}", "category": cat})
    return pd.DataFrame(rows)


def test_split_is_deterministic() -> None:
    """Re-running stratified_split with the same seeds yields identical hashes."""
    df = _make_synthetic_df(n_per_class=40)

    train1, val1, test1, holdout1 = stratified_split(df.copy())
    train2, val2, test2, holdout2 = stratified_split(df.copy())

    assert _content_hash(train1) == _content_hash(train2), "train hash differs"
    assert _content_hash(val1) == _content_hash(val2), "val hash differs"
    assert _content_hash(test1) == _content_hash(test2), "test hash differs"
    assert _content_hash(holdout1) == _content_hash(holdout2), "holdout hash differs"


def test_holdout_hash_stable() -> None:
    """The holdout hash must be stable (it becomes the model card data_hash)."""
    df = _make_synthetic_df(n_per_class=40)
    _, _, _, holdout1 = stratified_split(df.copy())
    _, _, _, holdout2 = stratified_split(df.copy())
    assert _content_hash(holdout1) == _content_hash(holdout2)


def test_no_overlap_between_splits() -> None:
    """Train / val / test / holdout must be disjoint."""
    df = _make_synthetic_df(n_per_class=40)
    train, val, test, holdout = stratified_split(df)

    sets = [
        set(zip(s["description"], s["category"]))
        for s in [train, val, test, holdout]
    ]
    names = ["train", "val", "test", "holdout"]
    for i, (a, na) in enumerate(zip(sets, names)):
        for j, (b, nb) in enumerate(zip(sets, names)):
            if i != j:
                overlap = a & b
                assert not overlap, f"{na} and {nb} share {len(overlap)} rows"


def test_all_categories_represented_in_splits() -> None:
    """Every taxonomy category appears in every split (stratification sanity)."""
    df = _make_synthetic_df(n_per_class=40)
    train, val, test, holdout = stratified_split(df)
    expected = set(TAXONOMY["categories"])
    for name, split in [("train", train), ("val", val), ("test", test), ("holdout", holdout)]:
        found = set(split["category"].unique())
        missing = expected - found
        assert not missing, f"{name} missing categories: {missing}"


def test_consolidation_map_applied(tmp_path: Path) -> None:
    """load_and_clean maps source labels via consolidation_map and drops the sentinel."""
    csv_path = tmp_path / "raw.csv"
    pd.DataFrame({
        "Transaction Description": ["buy groceries", "coffee run", "junk row", "explicit misc"],
        "Transaction Type": ["DEB", "DEB", "DEB", "DEB"],
        "Category": ["Grocery", "Restaurant", "UnknownLabel", "Misc Expenses"],
    }).to_csv(csv_path, index=False)

    df, stats = load_and_clean(csv_path, TAXONOMY)

    # Input text = description + bracketed type code.
    assert df.loc[df["category"] == "groceries", "description"].iloc[0] == "buy groceries [DEB]"
    assert (df["category"] == "groceries").any()
    assert (df["category"] == "dining").any()
    # UnknownLabel (unmapped) and "Misc Expenses"→other are dropped (other is a sentinel).
    assert "other" not in set(df["category"])
    assert not df["description"].str.startswith("junk row").any()
    assert not df["description"].str.startswith("explicit misc").any()
    assert stats["n_other_dropped"] == 2  # UnknownLabel + Misc Expenses
