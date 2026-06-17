# Tasks: Security & Compliance Hardening

**Input**: Design documents from `/specs/008-security-hardening/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/erasure.md, quickstart.md

## Phase 1: Setup

**Purpose**: Verify integration points and create the phase git branch.

- [ ] T001 Create and switch to git branch `008-security-hardening` from main

---

## Phase 2: Foundational

**Purpose**: Add the `RailRefusal` exception and update `chat.py` to catch it — the
one structural change that US1 implementation and all other phases depend on.

- [ ] T002 Add `RailRefusal(RaseedError)` exception class to `backend/app/core/exceptions.py` with `reason: str` field and `user_facing_message: str` property
- [ ] T003 Update `backend/app/api/chat.py` `_generate()` to catch `RailRefusal` from `check_input` and `check_output` and yield `{"error": "refusal", "reason": e.reason, "rail": "input|output"}` then return early

**Checkpoint**: Exception plumbing in place — rails can now raise and chat handles it.

---

## Phase 3: User Story 1 — Chat Safety Rails & PII Redaction (P1) 🎯 MVP

**Goal**: Fill the three no-op stubs in `rails.py`; PII never reaches logs or LLM.

**Independent Test**: `pytest tests/unit/test_rails.py -v` — all 8 rail/redaction
unit tests pass without DB, Redis, or LLM.

### Implementation

- [ ] T004 [US1] Fill `redact()` in `backend/app/services/agent/rails.py` with 6 compiled `re.compile` patterns (PAN, IBAN, UK phone, email, API key `sk-…`, Gemini `AIza…`) and return the redacted string; patterns compiled at module load
- [ ] T005 [US1] Fill `check_input()` in `backend/app/services/agent/rails.py` with ordered keyword checks: injection → jailbreak → extraction → off-domain; raise `RailRefusal(reason=<category>, user_facing_message=<plain text>)` on first match; return clean message if none fire
- [ ] T006 [US1] Fill `check_output()` in `backend/app/services/agent/rails.py` with output checks: licensed-advice keywords → raise `RailRefusal(reason="advice", user_facing_message=<disclaimer>)`; return text if clean
- [ ] T007 [US1] Write `backend/tests/unit/test_rails.py`: 8 tests — redact_card, redact_email, redact_api_key, input_injection_refused, input_jailbreak_refused, input_off_domain_refused, input_finance_passes, output_advice_refused

**Checkpoint**: US1 complete — rails live, PII redacted, refusals handled.

---

## Phase 4: User Story 2 — Red-team CI Gate (P2)

**Goal**: Committed probe suite as CI Gate #5; PII redaction pipeline gate as Gate #6 Part 1; catches rail and redaction regressions on every PR.

**Independent Test**: `pytest tests/test_redteam_gate.py -v` — all probes pass and
PII pipeline check passes; no DB/Redis/LLM required.

### Implementation

- [ ] T008 [US2] Create `backend/tests/fixtures/redteam_probes.json` with 10 probes (4 injection, 2 jailbreak, 2 extraction, 1 cross-user, 1 off-domain); each probe: `{id, category, payload, expected, attack_vector}`
- [ ] T009 [US2] Write `backend/tests/test_redteam_gate.py`: (a) Gate #5 — load probes from fixture, call `check_input(probe.payload)` for each `expected: "refused"` probe, assert `RailRefusal` is raised; assert `expected: "allowed"` probes do NOT raise; (b) Gate #6 Part 1 (FR-006) — call `redact()` on a message containing `4111111111111111` (test PAN) and `sk-testkey123`, assert neither raw string appears in the output, assert `[REDACTED-CARD]` and `[REDACTED-KEY]` appear; fully stack-independent
- [ ] T010 [US2] Add Gate #5 + Gate #6 Part 1 step to `.github/workflows/ci.yml`: `pytest tests/test_redteam_gate.py -q` under `working-directory: backend`, no stack required

**Checkpoint**: US2 complete — CI Gate #5 and Gate #6 Part 1 live and blocking.

---

## Phase 5: User Story 3 — Per-user Write Rate Limiting (P3)

**Goal**: Confirm `check_write_rate` covers the LLM-agent path (not just direct API).

**Independent Test**: `pytest tests/unit/test_write_tools.py::test_agent_write_rate_limit_via_llm_path -v`

### Implementation

- [ ] T011 [US3] Add `test_agent_write_rate_limit_via_llm_path` to `backend/tests/unit/test_write_tools.py`: patches `check_write_rate` to raise `RateLimitExceeded` after 10 calls, dispatches `reclassify_transaction` via `dispatch()` 11 times, asserts the 11th result contains `"error"` with "rate" or "limit" in the message (verifies the LLM-triggered path, not just a direct API call)

**Checkpoint**: US3 complete — write-tool rate limiting confirmed end-to-end.

---

## Phase 6: User Story 4 — Right to Erasure (P4)

**Goal**: One authenticated DELETE call purges all user data and writes an audit record.

**Independent Test**: `pytest tests/unit/test_erasure.py -v` — service logic verified
without live DB; stores queried return 0 rows; audit entry created.

### Implementation

- [ ] T012 [US4] Create `backend/app/domain/erasure_audit.py`: `ErasureAudit` SQLAlchemy model with fields `id, user_id, requested_at, completed_at, per_store_counts (JSONB), status`; NO RLS policy; import in `backend/app/domain/__init__.py`
- [ ] T013 [US4] Create `backend/alembic/versions/0006_security_hardening.py`: `upgrade()` creates `erasure_audit` table (no RLS, no FK cascade on purge); `downgrade()` drops it
- [ ] T014 [US4] Create `backend/app/schemas/erasure.py`: `ErasureResponse(BaseModel)` with `audit_id, status, deleted_counts, message`
- [ ] T015 [US4] Create `backend/app/services/erasure.py`: `ErasureService` with async `erase_user(user_id, session, redis)` method that hard-deletes rows from all 9 user-scoped tables in FK-safe order, then DELs all Redis keys matching `raseed:*:{user_id}`, writes `erasure_audit` row with `status=completed`, returns `ErasureResponse`; uses `asyncio.gather` for the Redis scan+del
- [ ] T016 [US4] Create `backend/app/api/erasure.py`: `DELETE /users/me/erasure` endpoint, `current_active_user` dependency, calls `ErasureService.erase_user()`, returns 202 with `ErasureResponse`
- [ ] T017 [US4] Register erasure router in `backend/app/main.py` (or `backend/app/api/__init__.py`)
- [ ] T018 [US4] Write `backend/tests/unit/test_erasure.py`: 4 tests — `test_erase_deletes_all_tables` (mock session, assert 9 DELETE calls), `test_erase_invalidates_redis_sessions` (mock redis scan+del), `test_erase_writes_audit_entry` (assert erasure_audit row created with status=completed), `test_erase_returns_correct_counts` (assert per_store_counts in response)
- [ ] T019 [P] [US4] Create `frontend/src/api/accountApi.ts`: `accountApi.requestErasure()` → `DELETE /users/me/erasure`, returns `ErasureResponse`
- [ ] T020 [P] [US4] Create `frontend/src/pages/Account.tsx`: account settings page with a "Delete My Account" section, confirmation dialog (requires typing "DELETE"), calls `accountApi.requestErasure()`, shows result or error; `data-testid="erasure-btn"`, `data-testid="erasure-confirm-input"`, `data-testid="erasure-result"`
- [ ] T021 [US4] Add `/account` route to `frontend/src/App.tsx` and "Account" link to `frontend/src/components/NavBar.tsx`
- [ ] T022 [US4] Write `frontend/src/pages/Account.test.tsx`: 3 tests — renders erasure button, confirmation input blocks accidental deletion, successful erasure shows result message

**Checkpoint**: US4 complete — erasure endpoint live, audit log written.

---

## Phase 7: User Story 5 — Vault Hardening & Secret Scan (P5)

**Goal**: Zero secrets in source; CI Gate #6 Part 2 secret-scan enforces this on every PR.

**Independent Test**: `pytest tests/test_secret_scan_gate.py -v` — grep over
`backend/`, `frontend/src/`, `prompts/` returns zero matches.

### Implementation

- [ ] T023 [US5] Create `backend/tests/test_secret_scan_gate.py`: pytest test that uses `subprocess.run(["git", "grep", "-rn", "--include=*.py", "--include=*.ts", "--include=*.tsx", "--include=*.txt", <pattern_list>], ...)` across `backend/app/`, `frontend/src/`, `prompts/`; fails if any output is produced; pattern list: `sk-`, `AIza`, `password\s*=\s*[\"']`, `secret\s*=\s*[\"']`; excludes `.venv/`, `node_modules/`, `tests/fixtures/`
- [ ] T024 [US5] Generate `.secrets.baseline` at repo root: run `detect-secrets scan backend/app/ frontend/src/ prompts/ > .secrets.baseline` from repo root; commit the baseline file
- [ ] T025 [US5] Add Gate #6 Part 2 step to `.github/workflows/ci.yml`: `pip install detect-secrets`, `detect-secrets scan --baseline .secrets.baseline backend/app/ frontend/src/ prompts/`, fail on any new secrets found; sequential after Gate #5 step
- [ ] T026 [US5] Create `SECURITY.md` at repo root covering all 4 required topics: (1) secret management via Vault + no hardcoded secrets policy; (2) PII redaction boundary (what is redacted, where, which call site); (3) model-unlearning limitation (plain English explanation); (4) vulnerability disclosure process (email + response SLA)

**Checkpoint**: US5 complete — secret scan gate live, SECURITY.md written.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T027 Append Phase 6 decision rows D10–D15 to `docs/DECISIONS.md` (decisions documented in plan.md Section "Decisions to Record")
- [ ] T028 [P] Run `pytest backend/tests/ -q` and confirm all existing tests still pass (no regressions from chat.py exception change)
- [ ] T029 [P] Run `npm run typecheck` and `npm run test -- --run` in `frontend/` to confirm no TypeScript or Vitest regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: No dependencies — start immediately
- **Foundational (T002–T003)**: Depends on T001; **BLOCKS all user stories**
- **US1 (T004–T007)**: Depends on T002–T003 (RailRefusal exception)
- **US2 (T008–T010)**: Depends on US1 (probes call `check_input`)
- **US3 (T011)**: Depends on T002–T003 (independent of US1 rails)
- **US4 (T012–T022)**: Independent of US1/US2/US3 (different code path); can run in parallel with US3
- **US5 (T023–T026)**: Independent of US1–US4 (grep-based, no runtime dependency)
- **Polish (T027–T029)**: Depends on all prior phases

### Within Each Phase

- T004, T005, T006 within US1: sequential (each builds on `rails.py`)
- T012, T014, T019 [P], T020 [P] in US4: some parallel opportunities marked
- T023 and T024 in US5: parallel

### Parallel Opportunities

All `[P]`-marked tasks within a phase can start simultaneously.
US3, US4, and US5 can start in parallel after the Foundational phase.

---

## Implementation Strategy

### MVP (US1 + US2 only)

1. T001 (branch)
2. T002–T003 (foundational)
3. T004–T007 (rails + unit tests)
4. T008–T010 (red-team + PII gate)
5. Validate: `pytest tests/unit/test_rails.py tests/test_redteam_gate.py -v`

### Full Delivery (sequential after MVP)

6. T011 (US3 rate-limit verification)
7. T012–T022 (US4 erasure — backend + frontend)
8. T023–T026 (US5 secret scan + SECURITY.md)
9. T027–T029 (polish)

---

## Notes

- Total tasks: 29 (T001–T029)
- US1: 4 implementation + 1 test = 5 tasks (MVP core)
- US2: 3 tasks (Gate #5 + Gate #6 Part 1)
- US3: 1 task (test-only, no new implementation)
- US4: 11 tasks (new table + service + endpoint + frontend)
- US5: 4 tasks (Gate #6 Part 2 + SECURITY.md)
- Polish: 3 tasks
- `check_write_rate` in `writes.py` already wired — no implementation task for the rate-limit mechanism itself
- Rails are pure Python `re` — no new package install needed in the serving image
- `detect-secrets` is CI-only: installed in the CI step, never added to `requirements.txt`
- FR-006 (PII pipeline gate) covered in T009 as Gate #6 Part 1 inside `test_redteam_gate.py`
