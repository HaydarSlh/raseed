"""Drift simulation: loads the committed skewed batch fixture, invokes the monitor on-demand, prints fired signals.

Usage:
    cd backend
    python scripts/simulate_drift.py

Scenario 5 from quickstart.md — isolated from real data (uses fixture, not live DB writes).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "drift_skewed_batch.parquet"


async def main() -> None:
    from app.workers.drift import compute_drift_signals, compute_new_merchant_rate, compute_psi
    from app.core.config import get_settings

    if not FIXTURE_PATH.exists():
        print(f"ERROR: fixture not found at {FIXTURE_PATH}")
        print("Run: python backend/scripts/create_drift_fixture.py")
        sys.exit(1)

    df = pd.read_parquet(FIXTURE_PATH)
    settings = get_settings()

    mean_confidence = float(df["confidence"].mean())
    merchants = set(df["merchant"].dropna().tolist())

    # Compute category histogram from skewed batch
    total = len(df)
    cat_counts = df["category"].value_counts().to_dict()
    current_hist = {cat: count / total for cat, count in cat_counts.items()}

    # Training reference: balanced distribution (simulating a well-trained model)
    training_hist = {
        "groceries": 0.20,
        "dine_out": 0.15,
        "bills": 0.15,
        "travel": 0.10,
        "other_shopping": 0.10,
        "savings": 0.10,
        "income": 0.10,
        "cash": 0.10,
    }
    training_merchants = {"TESCO", "AMAZON", "UBER", "NETFLIX", "SAINSBURY"}

    correction_rate = 0.05  # simulated — no real corrections DB in simulation mode

    psi = compute_psi(current_hist, training_hist)
    new_merchant_rate = compute_new_merchant_rate(merchants, training_merchants)

    outcome = compute_drift_signals(
        mean_confidence=mean_confidence,
        correction_rate=correction_rate,
        psi=psi,
        new_merchant_rate=new_merchant_rate,
        category_histogram=current_hist,
        training_histogram=training_hist,
        seen_merchants=training_merchants,
        window_merchants=merchants,
        settings=settings,
    )

    print("\n=== Drift Simulation ===")
    print(f"  Fixture rows:        {len(df)}")
    print(f"  Mean confidence:     {mean_confidence:.4f}  (threshold: {settings.drift_mean_confidence_min})")
    print(f"  Correction rate:     {correction_rate:.4f}  (threshold: {settings.drift_correction_rate_max})")
    print(f"  PSI:                 {psi:.4f}  (threshold: {settings.drift_psi_max})")
    print(f"  New merchant rate:   {new_merchant_rate:.4f}  (threshold: {settings.drift_new_merchant_rate_max})")
    print(f"\n  fired:               {outcome['fired']}")
    print(f"  fired_signals:       {outcome['fired_signals']}")
    print(f"  triggered_retrain:   {outcome['triggered_retrain']}")

    if outcome["triggered_retrain"]:
        print("\n  [GATE #7 WOULD PASS] — primary signal crossed, retrain would be enqueued.")
    elif outcome["fired"]:
        print("\n  [SECONDARY ALARM] — alarm fired, Slack alert would be sent, no retrain.")
    else:
        print("\n  [NO DRIFT DETECTED]")

    return outcome


if __name__ == "__main__":
    asyncio.run(main())
