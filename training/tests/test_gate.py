"""T021 — Gate mechanism tests (US2).

Uses stand-in result sets (no network, no services, no LFS required) to verify the
gate's pass/fail logic. Refs: ci-gate.md, FR-020, FR-020a, FR-021, FR-022, SC-005.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

CATEGORIES = [
    "groceries", "dining", "transport", "utilities", "healthcare",
    "entertainment", "shopping", "travel", "education", "income",
    "transfer", "fees", "other",
]
N_CATS = len(CATEGORIES)
# 100 samples/class so a target macro-F1 maps to a per-class correct count with no
# coarse-rounding error (200/13 ≈ 15 was too coarse to hit the target F1 reliably).
N_HOLDOUT = N_CATS * 100

THRESHOLDS_BASE = {
    "categorizer": {
        "macro_f1_min": 0.70,
        "beat_baseline_margin": 0.03,
        "min_per_class_f1": 0.50,
        "max_inference_latency_ms": 200,
        "operating_thresholds": {cat: 0.5 for cat in CATEGORIES},
    }
}


def _make_holdout(tmp: Path, n: int = N_HOLDOUT) -> Path:
    """Minimal holdout.parquet with balanced classes."""

    rows_per_class = max(1, n // N_CATS)
    cats = (CATEGORIES * (rows_per_class + 1))[:n]
    df = pd.DataFrame({
        "description": [f"tx {i}" for i in range(n)],
        "category": cats,
    })
    path = tmp / "holdout.parquet"
    df.to_parquet(path, index=False)
    return path


def _make_predictions(holdout_path: Path, f1: float) -> Path:
    """Write predictions whose per-class (and hence macro) F1 ≈ `f1`.

    Stratified per class: make round(f1 * class_count) of each class correct and route
    the rest to the *next* category. With balanced classes this yields per-class
    precision = recall = f1 exactly, so macro-F1 and min-per-class-F1 are predictable.
    """
    from collections import defaultdict

    holdout = pd.read_parquet(holdout_path)
    labels = holdout["category"].tolist()

    counts: dict[str, int] = defaultdict(int)
    for lab in labels:
        counts[lab] += 1
    target_correct = {c: round(f1 * n) for c, n in counts.items()}

    seen: dict[str, int] = defaultdict(int)
    preds = []
    for lab in labels:
        seen[lab] += 1
        if seen[lab] <= target_correct[lab]:
            preds.append(lab)
        else:
            nxt = (CATEGORIES.index(lab) + 1) % len(CATEGORIES)
            preds.append(CATEGORIES[nxt])

    pred_path = holdout_path.parent / f"preds_{f1:.2f}.parquet"
    pd.DataFrame({"category": preds}).to_parquet(pred_path, index=False)
    return pred_path


def _run_gate(holdout: Path, champion_preds: Path, baseline_preds: Path, thresholds: Path) -> int:
    """Call gate_holdout.gate() and return exit code."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gate_holdout",
        Path(__file__).parents[1] / "gate_holdout.py",  # training/gate_holdout.py
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.gate(
        holdout_path=holdout,
        champion_pred_path=champion_preds,
        baseline_pred_path=baseline_preds,
        thresholds_path=thresholds,
        taxonomy_path=None,  # gate loads taxonomy from thresholds only for tests
        latency_ms=50.0,  # well within limit
    )


@pytest.fixture()
def gate_env(tmp_path: Path):
    """Build a minimal gate environment with good stand-in models."""
    holdout = _make_holdout(tmp_path)
    thresholds_path = tmp_path / "eval_thresholds.yaml"
    with thresholds_path.open("w") as f:
        yaml.dump(THRESHOLDS_BASE, f)
    return {"tmp": tmp_path, "holdout": holdout, "thresholds": thresholds_path}


def test_gate_passes_good_champion(gate_env) -> None:
    """Champion beats baseline by margin and clears floor → exit 0."""
    holdout = gate_env["holdout"]
    champion = _make_predictions(holdout, f1=0.82)   # 0.82 ≥ 0.70 floor, beats 0.79 by 0.03
    baseline = _make_predictions(holdout, f1=0.79)
    thresholds = gate_env["thresholds"]
    code = _run_gate(holdout, champion, baseline, thresholds)
    assert code == 0, f"Gate should PASS but returned {code}"


def test_gate_fails_below_floor(gate_env) -> None:
    """Champion below macro_f1_min floor → non-zero exit."""
    holdout = gate_env["holdout"]
    champion = _make_predictions(holdout, f1=0.65)   # below 0.70 floor
    baseline = _make_predictions(holdout, f1=0.60)
    thresholds = gate_env["thresholds"]
    code = _run_gate(holdout, champion, baseline, thresholds)
    assert code != 0, "Gate should FAIL (below floor) but returned 0"


def test_gate_fails_insufficient_margin(gate_env) -> None:
    """Champion above floor but doesn't beat baseline by required margin → fail."""
    holdout = gate_env["holdout"]
    champion = _make_predictions(holdout, f1=0.80)   # above 0.70 floor
    baseline = _make_predictions(holdout, f1=0.78)   # margin=0.02 < 0.03 required
    thresholds = gate_env["thresholds"]
    code = _run_gate(holdout, champion, baseline, thresholds)
    assert code != 0, "Gate should FAIL (insufficient margin) but returned 0"


def test_gate_no_network_calls(gate_env, monkeypatch) -> None:
    """Gate must make no network/service calls (FR-021)."""
    import socket

    def _fail_connect(*args, **kwargs):
        raise AssertionError("gate_holdout.py made a network call — FR-021 violation")

    monkeypatch.setattr(socket.socket, "connect", _fail_connect)

    holdout = gate_env["holdout"]
    champion = _make_predictions(holdout, f1=0.82)
    baseline = _make_predictions(holdout, f1=0.79)
    thresholds = gate_env["thresholds"]
    # Should complete without triggering _fail_connect
    _run_gate(holdout, champion, baseline, thresholds)
