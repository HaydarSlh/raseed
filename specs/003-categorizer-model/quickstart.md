# Quickstart — Categorizer (Phase 2 validation)

Runnable scenarios proving the phase's acceptance criteria. Contracts:
[predict-api.md](./contracts/predict-api.md),
[model-artifact.md](./contracts/model-artifact.md),
[ci-gate.md](./contracts/ci-gate.md). Data shapes: [data-model.md](./data-model.md).

## Prerequisites
- The champion artifact bundle committed under `modelserver/artifacts/` (LFS), with
  `model_card.md` and the pinned SHA-256.
- `git lfs install && git lfs pull` so `*.onnx` / `*.parquet` are real files.
- `eval_thresholds.yaml` `categorizer` block filled with real numbers.

## Scenario 1 — Serve & predict (US1, SC-001)
```bash
docker compose up -d modelserver
curl -s http://localhost:8080/healthz            # → status ok, model loaded, sha256 pinned
curl -s -X POST http://localhost:8080/predict \
  -H 'content-type: application/json' \
  -d '{"description":"STARBUCKS STORE #1234 SEATTLE WA","top_k":3}'
```
**Expect**: a `category` in the taxonomy, calibrated `confidence` ∈ [0,1], ranked
`alternatives`, `low_confidence` boolean. p95 < 200 ms over a small loop.

## Scenario 2 — Refuse-to-boot (US1, SC-004)
```bash
# (a) missing artifact
docker compose run --rm -e CATEGORIZER_ARTIFACT=/nonexistent.onnx modelserver  # → non-zero exit / not ready
# (b) hash mismatch: point the server at a tampered/other onnx
docker compose run --rm -v "$PWD/tests/fixtures/wrong.onnx:/app/artifacts/categorizer.onnx" modelserver  # → non-zero exit
```
**Expect**: the process never serves; `/healthz` never reports ready.

## Scenario 3 — Low-confidence routing (US1, FR-010)
Send a deliberately ambiguous/garbled description whose top score is below its
category threshold:
```bash
curl -s -X POST http://localhost:8080/predict -H 'content-type: application/json' \
  -d '{"description":"xfer 99213 ###"}'
```
**Expect**: still returns a best category, but `low_confidence: true`.

## Scenario 4 — CI gate, locally (US2, SC-005)
```bash
python training/gate_holdout.py            # exit 0 when champion beats baseline by margin AND ≥ floor
# degrade check: temporarily swap in the baseline as the champion → gate must FAIL (exit non-zero)
```
**Expect**: pass on the real champion; fail (blocks merge) on a degraded model;
**no** modelserver/backend/compose is started by the gate.

## Scenario 5 — Reproducible split (US3, SC-009)
```bash
python training/prepare_dataset.py --out /tmp/split_a
python training/prepare_dataset.py --out /tmp/split_b
diff <(jq .hashes /tmp/split_a/split_manifest.json) <(jq .hashes /tmp/split_b/split_manifest.json)  # → identical
```
**Expect**: identical per-split content hashes; `holdout` hash == model card
`data_hash`.

## Scenario 6 — Lean serving image (US1, SC-007)
```bash
docker compose build modelserver
docker run --rm --entrypoint pip raseed-modelserver freeze | grep -Ei 'torch|transformers|scikit' && echo "LEAK" || echo "lean ✓"
```
**Expect**: `lean ✓` — no torch / transformers / scikit-learn in the serving image.

## Scenario 7 — Three-way comparison recorded (US3, SC-006)
Open `docs/DECISIONS.md` and confirm a row table with macro-F1, per-class F1,
latency, and cost-per-call for **all three** approaches, plus the winner rule, the
per-class threshold rule, and the seeded floor.

## Acceptance roll-up
- US1: Scenarios 1–3, 6 green.  US2: Scenario 4 green (+ CI job green).
- US3: Scenarios 5, 7 green; model card fields present and SHA matches the artifact.
