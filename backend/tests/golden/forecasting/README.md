# Golden Fixture — Forecaster CI Gate

This directory contains committed fixtures for CI gate #2 (constitution Art. V, R9).

## Contents

- `history.parquet` — synthetic multi-user daily-transaction history (generated once, committed).
- `expected_horizon.parquet` — the expected 30-day balance trajectory for each user.
- `generate_fixture.py` — one-shot script to (re)generate the fixtures (run locally, not in CI).

## Gate logic

CI runs `backend/tests/test_forecaster_gate.py`, which:
1. Loads history and expected horizon from this directory.
2. Fits the forecaster on history.
3. Computes forecaster MAE vs day-of-week baseline MAE.
4. Fails the build if `forecaster_mae > baseline_mae`.

## Regenerating fixtures

Only regenerate when the forecasting algorithm fundamentally changes AND you have confirmed
the new algorithm produces lower MAE on the held-out test split. Run:

```
python backend/tests/golden/forecasting/generate_fixture.py
```

Commit the new `.parquet` files alongside the code change.
