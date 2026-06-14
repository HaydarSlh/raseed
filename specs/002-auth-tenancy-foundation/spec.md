# Feature Specification: Foundation — Auth, Tenancy & the Infra Spine

**Feature Branch**: `002-auth-tenancy-foundation`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "briefs/phase-1-foundation.md — A user can register and log in, and every database access is isolated per user at the database layer, with the cross-cutting infrastructure (config, logging, tracing, errors, secrets, model gateway) in place."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register and sign in (Priority: P1)

A new person creates an account with an email and password, then signs in and
receives a session that identifies them on every subsequent request. The identity
in that session is the only thing that determines whose data they can reach.

**Why this priority**: Without an authenticated identity there is no one to isolate
data for; every other guarantee in this phase hangs off a verified identity. It is
the foundational MVP slice.

**Independent Test**: From the application shell, register a new account, sign in,
and confirm an authenticated session is established and a protected request
succeeds while an unauthenticated one is rejected.

**Acceptance Scenarios**:

1. **Given** no existing account, **When** a person registers with a valid email
   and password, **Then** an account is created and they can sign in.
2. **Given** a registered account, **When** they sign in with correct credentials,
   **Then** they receive a valid session usable on protected requests.
3. **Given** wrong credentials, **When** sign-in is attempted, **Then** it is
   rejected with a clear, non-revealing error and no session is issued.
4. **Given** a protected request, **When** it arrives without a valid session,
   **Then** it is rejected.
5. **Given** a request, **When** the identity is determined, **Then** it is taken
   only from the verified session — never from any value supplied in the request
   body.

---

### User Story 2 - Database-enforced per-user isolation (Priority: P1)

Each person can read and write only their own records. This isolation is enforced
by the database itself, so that even if an application query forgets to filter by
the current user, the database still returns nothing belonging to anyone else.

**Why this priority**: Per-user isolation is the platform's core trust contract and
the phase's headline guarantee; a single leak compromises every user at once. It is
co-critical with authentication.

**Independent Test**: Seed two users with rows, set the request identity to User A,
and attempt to read User B's rows through a deliberately *unscoped* data-access call
— confirm zero rows of User B are returned. Then confirm the per-request identity
context is cleared between reused connections so no identity bleeds into the next
request.

**Acceptance Scenarios**:

1. **Given** two users each owning rows, **When** User A issues any read, **Then**
   only User A's rows are ever returned.
2. **Given** a data-access call that deliberately omits the user filter, **When**
   it runs under User A's identity, **Then** the database still returns none of
   User B's rows.
3. **Given** a pooled/reused connection, **When** one request completes and the
   next begins, **Then** the per-request identity context has been reset and does
   not carry over.
4. **Given** every table that holds user data, **When** the schema is inspected,
   **Then** each row is attributable to a user and isolation is enforced at the
   database layer.
5. **Given** the background statistics role (used only by a later-phase privileged
   job), **When** it is defined, **Then** it is the sole identity permitted to read
   across users, and ordinary user sessions can never compute cross-user results.

---

### User Story 3 - A reliable infrastructure spine (Priority: P2)

Operators can run the service with confidence that configuration is validated,
secrets are present, every request is traceable, and all calls to any external
hosted model go through one auditable gateway. The service refuses to start in an
unsafe configuration rather than running degraded.

**Why this priority**: The cross-cutting spine makes the system operable and
debuggable and prevents silent misconfiguration, but it depends on identity and
isolation existing to be meaningful. It is essential but second to the security
guarantees.

**Independent Test**: Start the service with a required secret missing and confirm
it fails loudly at startup; start it again with the example configuration defaults
and confirm it boots. Trigger an operation that logs and confirm the log line is
structured and carries a request identifier. Route a model call and confirm it
flows through the single gateway with retry/timeout behavior.

**Acceptance Scenarios**:

1. **Given** a required secret is missing, **When** the service starts, **Then** it
   fails loudly at startup with a clear message and does not serve traffic.
2. **Given** the example configuration defaults, **When** the service starts,
   **Then** it boots successfully.
3. **Given** an unknown/unexpected configuration key, **When** the service starts,
   **Then** it is rejected rather than silently ignored.
4. **Given** any handled request, **When** it produces logs, **Then** the logs are
   structured and correlated by a per-request identifier across the service and its
   background worker.
5. **Given** any call to a hosted model, **When** it is made, **Then** it passes
   through the single model gateway (with timeout and bounded retry, and a defined
   failover order) and no other code path calls a hosted model directly.
6. **Given** a transient external failure, **When** a model/gateway call is
   retried, **Then** client errors are not retried and failures surface as
   structured errors, never raw stack traces to the user.

---

### Edge Cases

- **Duplicate registration**: registering an email that already exists is rejected
  with a clear, non-revealing message.
- **Missing/expired session**: protected requests without a valid, unexpired
  session are rejected uniformly.
- **Identity spoofing attempt**: a request that supplies a user identifier in its
  body is ignored; only the verified session identity is used.
- **Connection reuse leakage**: the per-request identity context must be reset on
  release so a pooled connection never serves the wrong user.
- **Partial secret set**: if some but not all required secrets are present, startup
  still fails loudly rather than booting half-configured.
- **External model outage**: when the primary model is unavailable, the gateway
  fails over per the defined order; if all fail, the caller gets a structured error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let a person register with an email and password and
  subsequently authenticate to obtain a session.
- **FR-002**: The system MUST derive the acting user's identity solely from the
  verified session, never from request-supplied values.
- **FR-003**: The system MUST reject protected requests that lack a valid session
  and MUST reject sign-in with incorrect credentials using a clear, non-revealing
  error.
- **FR-004**: Every record that holds user data MUST be attributable to exactly one
  user.
- **FR-005**: The system MUST enforce per-user data isolation at the database layer
  such that a query which omits the user filter still cannot return another user's
  rows; application-layer user scoping MUST remain in place as defense in depth.
- **FR-006**: The per-request user-identity context MUST be set from the verified
  session at the start of a request and MUST be reset when the underlying
  connection is released, so reused connections never carry identity across
  requests.
- **FR-007**: The system MUST define exactly one privileged identity permitted to
  read across users, reserved for a later-phase background statistics job; ordinary
  user sessions MUST NOT be able to compute cross-user aggregates.
- **FR-008**: The system MUST provide the foundational data structures for later
  phases — users; transactions carrying a label-provenance value
  (`rule | model | llm | human`), a confidence value, and a needs-review flag;
  goals; corrections; a model registry; and memory/audit records — all user-scoped
  and isolated per FR-005.
- **FR-009**: The system MUST validate configuration at startup from a single typed
  source, rejecting unknown keys and failing fast when a required value is absent.
- **FR-010**: The system MUST resolve secrets from the secrets store at startup and
  MUST refuse to boot if a required secret is missing (the example-defaults path is
  an explicitly documented fallback, not a silent default).
- **FR-011**: The system MUST emit structured logs correlated by a per-request
  identifier across the service and its background worker, and MUST provide a
  tracing-span utility and a timeout/retry helper for external calls.
- **FR-012**: The system MUST map domain errors to structured responses; users MUST
  never see a raw stack trace.
- **FR-013**: All calls to any hosted external model MUST go through a single model
  gateway that applies timeout and bounded retry (client errors not retried) with a
  defined failover order; no other code path may call a hosted model directly.
- **FR-014**: The system MUST provide a fake model double so that automated tests
  never depend on a live external model.
- **FR-015**: The registration and sign-in flow MUST work end-to-end from the
  application shell.
- **FR-016**: The isolation guarantees (FR-005, FR-006) MUST be proven by automated
  tests that run in continuous integration.

### Key Entities

- **User**: An authenticated person; has an email, credentials, and an operator
  flag distinguishing ordinary users from operators. Owns all their data.
- **Transaction**: A user-owned financial record carrying label provenance
  (`rule | model | llm | human`), a confidence value, and a needs-review flag.
  (Only the structure is established this phase; ingestion/categorization come
  later.)
- **Goal**: A user-owned savings/spending goal record (structure only this phase).
- **Correction**: A user-confirmed label correction record — the future source of
  human-confirmed training data (structure only this phase).
- **Model Registry Entry**: A record describing a model version (card, identifier,
  status). Not user-scoped; governs serving in later phases (structure only).
- **Memory / Audit Record**: User-scoped long-term-memory and audit-log records
  (structure only this phase).
- **Request Identity Context**: The per-request binding of the verified user to the
  database session that drives isolation; set on request start, reset on release.
- **Privileged Statistics Identity**: The single cross-user identity reserved for a
  later background job; never available to user sessions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can go from no account to an authenticated session
  (register → sign in) end-to-end from the application shell.
- **SC-002**: 100% of attempts by one user to read another user's rows return zero
  foreign rows — including through a deliberately unscoped data-access call.
- **SC-003**: Across repeated pooled requests, the per-request identity context
  carries over 0% of the time (verified by an automated reset test).
- **SC-004**: Starting with any required secret missing fails at startup 100% of the
  time; starting with the example-defaults configuration boots successfully.
- **SC-005**: An unknown configuration key prevents startup 100% of the time.
- **SC-006**: 100% of handled requests emit structured logs carrying a per-request
  identifier.
- **SC-007**: 100% of hosted-model calls flow through the single gateway; a repo-wide
  check finds no direct hosted-model call outside it.
- **SC-008**: The isolation and reset guarantees are covered by automated tests that
  pass in continuous integration.
- **SC-009**: Every user-data table has a per-user owner column and database-layer
  isolation enabled (verifiable by schema inspection).

## Assumptions

- The intended users are end users (who register/sign in) and operators (who run
  the service); "operator" is a simple flag, not a full role hierarchy.
- Email-based account verification, password reset, and multi-factor auth are out of
  scope for this phase (no outbound email service exists yet); standard
  email/password sign-in with a verified session token is sufficient.
- Session lifetime and refresh follow standard secure web-app defaults; exact
  durations are an implementation detail resolved at planning.
- Frontend work is limited to the minimal register/sign-in screens needed to prove
  the end-to-end flow; no other UI is in scope.
- No ML, ingestion, agent, or analytics behavior is built this phase — only the
  data structures those phases will use.
- The fixed technology stack and authoritative documents named in the project's
  governing context (constitution, `docs/PLAN.md`) apply; this phase chooses no new
  technologies.
- The example-defaults configuration is acceptable for local boot; production
  secrets always come from the secrets store.
