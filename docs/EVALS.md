# Raseed Evaluation Results

All eight CI gates with committed thresholds and measured values.

| Gate | Description | Threshold Key | Committed Value | Last Measured | CI Status | Notes |
|------|-------------|---------------|-----------------|---------------|-----------|-------|
| **Gate 1** | Categorizer macro-F1 on frozen holdout | `categorizer.macro_f1_min` | ≥ 0.84 | 0.8934 | ✅ PASS | TF-IDF+LR champion; DistilBERT (0.8677) lost and was blocked |
| **Gate 2** | Forecaster MAE ≤ day-of-week baseline | `forecaster.beat_baseline` | `true` | PASS | ✅ PASS | Prophet beats naïve DoW baseline on golden fixture |
| **Gate 3** | Tool-selection accuracy on 15-case golden set | `router.tool_selection_accuracy_min` | ≥ 0.80 (12/15) | — | ✅ PASS | FakeEmbedder; deterministic router + agent tool dispatch |
| **Gate 4** | RAG hit@5 and MRR on 15 triples | `rag.hit_at_5_min` | 0.0 | 0.0 | ✅ PASS [¹] | FakeEmbedder: non-semantic vectors; gate verifies plumbing, not quality |
| **Gate 5** | Red-team probes refused (10/10) | `redteam.max_injection_success_rate` | 0.0 | 0.0 | ✅ PASS | 12-probe fixture; 10 refused, 2 allowed |
| **Gate 6** | PII never reaches LLM; no hardcoded secrets | `redaction.pii_leak_count_max` | 0 | 0 | ✅ PASS | 6 PII patterns; detect-secrets baseline committed |
| **Gate 7** | Drift fires on simulated skewed batch | `drift.must_fire_on_simulated_drift` | `true` | PASS | ✅ PASS | drift_skewed_batch.parquet; mean confidence < 0.70 triggers alert |
| **Gate 8** | Compose smoke: all default services healthy | `compose_smoke.all_default_services_healthy` | `true` | PASS (local) | ⚠️ [²] | Runs on push to main only; skipped if Docker unavailable in CI |

---

[¹] **RAG threshold note**: `hit_at_5_min` and `mrr_min` are set to 0.0 intentionally.
The CI gate uses a `FakeEmbedder` that produces hash-seeded, non-semantic vectors. The
gate verifies that the retrieval pipeline is correctly wired (passages are indexed and
retrieved without errors), not that results are semantically relevant. Semantic quality
is verified by quickstart Scenario 7 (real embedder, running stack). Inflating the
threshold with a fake-positive value would misrepresent the gate's actual guarantee
(DECISIONS.md D18).

[²] **Gate 8 exemption**: Gate 8 is the only gate that requires a running stack. It runs
as a separate `compose-smoke` CI job, triggered only on push to main (not on PRs). If
Docker is unavailable in the CI runner, the `@pytest.mark.integration` test is skipped.
This is the documented exception to the stack-independent CI rule (constitution Art. V;
DECISIONS.md D17).

---

## How to reproduce all gate results

```bash
cd backend

# Gates 1–7 (stack-independent, ~30s)
pytest tests/test_forecaster_gate.py tests/test_tool_selection_gate.py \
       tests/test_rag_gate.py tests/test_redteam_gate.py \
       tests/test_secret_scan_gate.py tests/test_drift_gate.py -v

# Gate 1 (categorizer, separate runner)
python ../training/gate_holdout.py

# Gate 8 (requires Docker)
pytest tests/test_compose_smoke.py -m integration -v
```
