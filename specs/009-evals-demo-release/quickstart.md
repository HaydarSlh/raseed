# Quickstart: Evals, Demo & Release Validation

Seven end-to-end scenarios that prove Phase 7 is complete.

---

## Prerequisites

```bash
git clone https://github.com/HaydarSlh/raseed.git
cd raseed
cp .env.example .env
```

For scenarios 1–6 (stack-independent): only Python 3.12 and `pip install -r
backend/requirements-dev.txt` are required.

For scenario 7 (full demo): Docker and Docker Compose are required.

---

## Scenario 1 — All 8 CI gates pass

**What it proves**: FR-001 through FR-010; SC-001

```bash
cd backend

# Gates 1–7 (stack-independent)
pytest tests/test_categorizer_gate.py \
       tests/test_forecaster_gate.py \
       tests/test_tool_selection_gate.py \
       tests/test_rag_gate.py \
       tests/test_redteam_gate.py \
       tests/test_secret_scan_gate.py \
       tests/test_drift_gate.py \
       -v

# Gate 8 (requires Docker)
pytest tests/test_compose_smoke.py -m integration -v
```

**Expected outcome**: All tests PASS. Each gate test reads its threshold from
`eval_thresholds.yaml` and prints the measured value alongside the threshold.

---

## Scenario 2 — Gate 1 measures categorizer F1

**What it proves**: FR-003; R1; macro-F1 ≥ 0.84 on the committed holdout

```bash
cd backend
pytest tests/test_categorizer_gate.py -v -s
```

**Expected output** (example):
```
Gate 1 — Categorizer F1: measured=0.8934, threshold=0.84 → PASS
```

---

## Scenario 3 — Demo users seeded

**What it proves**: FR-011; SC-002

```bash
# With the stack running:
docker compose up -d postgres redis
python scripts/seed_demo.py
```

**Expected outcome**: Script prints `Seeded 2 demo users with 6 months of transactions`
and exits 0. Re-running is idempotent (no duplicates).

---

## Scenario 4 — Drift → retrain → promote rehearsal

**What it proves**: FR-012; SC-003

```bash
docker compose up -d
python backend/scripts/simulate_drift.py
```

**Expected outcome**: Slack webhook receives a drift alert; a retrain RQ job is
queued; the champion/challenger gate reports PASS or BLOCK (depending on score).

---

## Scenario 5 — Documentation completeness

**What it proves**: FR-013 through FR-016; SC-005

```bash
python -c "
import re, pathlib
required = {
    'docs/DESIGN.md': ['## Scaling story', '## Isolation', '## ML lifecycle'],
    'docs/EVALS.md': ['Gate 1', 'Gate 8'],
    'docs/RUNBOOK.md': ['## Startup', '## Secret rotation', '## Retraining', '## Erasure'],
    'docs/DECISIONS.md': [],
    'SECURITY.md': ['## Secret Management', '## PII Redaction'],
}
for path, sections in required.items():
    content = pathlib.Path(path).read_text()
    for s in sections:
        assert s in content, f'Missing section {s!r} in {path}'
    print(f'OK: {path}')
print('All documentation complete.')
"
```

**Expected outcome**: All five files print `OK:` and `All documentation complete.`

---

## Scenario 6 — README submission block filled

**What it proves**: FR-017; SC-008

```bash
python -c "
import pathlib
readme = pathlib.Path('README.md').read_text()
assert 'Gate 1' in readme, 'Submission block missing Gate 1'
assert 'Gate 8' in readme, 'Submission block missing Gate 8'
assert 'TBD' not in readme, 'Submission block contains TBD placeholders'
print('README submission block: OK')
"
```

---

## Scenario 7 — Fresh-clone demo

**What it proves**: FR-001 (full pipeline), SC-004; acceptance criterion

```bash
git clone https://github.com/HaydarSlh/raseed.git raseed-fresh
cd raseed-fresh
cp .env.example .env
docker compose up
# Wait for all services to report healthy (< 5 minutes)
# Open http://localhost:5173 in a browser
# Log in as demo@raseed.app / Demo1234!
# Ask: "What is my biggest spending category this month?"
```

**Expected outcome**: UI loads; agent responds with a category breakdown drawn
from the seeded transaction history; no errors in the compose logs.
