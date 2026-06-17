"""One-time script to generate the committed drift fixture for tests and CI Gate #7.

Run: python backend/scripts/create_drift_fixture.py
Writes: backend/tests/fixtures/drift_skewed_batch.parquet
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

UNKNOWN_MERCHANTS = [
    "UNFAMILIAR_SHOP_XQ91",
    "NEW_STORE_ZZ99",
    "MERCHANT_NEVER_SEEN_AB12",
    "FOREIGN_MARKET_KK55",
    "UNKNOWN_VENDOR_YY03",
]

KNOWN_CATEGORIES = ["groceries", "dine_out", "bills", "travel", "other_shopping"]

rng = random.Random(42)

rows = []
for i in range(200):
    merchant = rng.choice(UNKNOWN_MERCHANTS)
    cat = rng.choice(KNOWN_CATEGORIES)
    confidence = rng.uniform(0.20, 0.45)  # deliberately low — unfamiliar merchants
    rows.append({
        "description": f"{merchant} TXN{i:04d}",
        "merchant": merchant,
        "category": cat,
        "confidence": round(confidence, 4),
        "provenance": "model",
        "needs_review": confidence < 0.65,
    })

df = pd.DataFrame(rows)
out_path = Path(__file__).parent.parent / "tests" / "fixtures" / "drift_skewed_batch.parquet"
out_path.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(out_path, index=False)
print(f"Written {len(df)} rows to {out_path}")
