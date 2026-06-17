# Feature Specification: Knowledge & the Agent

**Feature Branch**: `006-agent-rag`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "briefs/phase-4-agent-rag.md — A user chats with an
agent that answers grounded money questions by combining exact queries over their
own data with cited financial-knowledge retrieval. Deterministic router for
enumerable turns; bounded tool-calling agent for ambiguous/multi-step turns; RAG
over a shared financial-literacy corpus with citations and a no-answer gate;
goals, session and durable memory; streamed chat UI; no-op rails hook points."

## Clarifications

### Session 2026-06-17

- Q: Are past conversations stored and browsable, or is chat ephemeral? → A: Ephemeral
  chat — the conversation lives only for the active session (short-term session
  context); no persisted transcript and no past-conversation browsing. Goals and
  explicit durable memories are the only persisted artifacts.
- Q: What are the agent's iteration and token caps per turn? → A: Max 8 tool-calling
  iterations and a ~16k-token total budget per turn; on reaching either cap the agent
  returns its best bounded answer.
- Q: How long does idle short-term conversation context survive before expiring? → A:
  30 minutes of inactivity.
- Q: What per-user write rate triggers throttling for agent-performed writes? → A: 10
  writes per minute per user.
- Q: What does a goal minimally require, and does it carry a status? → A: Required
  fields are name, target amount, and target date; status is one of active / achieved /
  abandoned.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask about my own money and get an exact answer (Priority: P1)

A signed-in user opens a chat, types a plain-language question about their own
finances ("What's my current balance?", "What am I subscribed to?", "How much did
I spend on groceries last month?"), and gets back a precise answer computed from
their own transaction data, streamed back as it is produced.

**Why this priority**: This is the core loop and the minimum viable slice — a user
can converse with their money and get trustworthy, exact answers. Without it there
is no agent product. Simple enumerable questions must be answered correctly and
cheaply (without invoking the full reasoning agent) to be fast and reliable.

**Independent Test**: With a seeded account, ask each of the enumerable questions
(balance, subscriptions, a single category total) and confirm the answer matches
the figure computed directly from the user's data, and that the response streams
rather than appearing only when complete.

**Acceptance Scenarios**:

1. **Given** a signed-in user with imported transactions, **When** they ask "What
   is my balance?", **Then** they receive the exact balance derived from their own
   data, and the figure is not fabricated or approximated.
2. **Given** a signed-in user, **When** they ask an enumerable question (balance,
   subscriptions list, or a simple category total), **Then** the system answers it
   directly via an exact query and template without engaging the reasoning agent.
3. **Given** any chat answer, **When** the system responds, **Then** the response
   is streamed incrementally to the user.
4. **Given** a user who is not signed in, **When** they attempt to use the chat,
   **Then** they are refused and directed to sign in, and no data is returned.
5. **Given** any answer that states a personal figure, **When** it is produced,
   **Then** that figure originates from an exact query over the user's data, never
   from retrieved knowledge text.

---

### User Story 2 - Get cited financial-literacy guidance (Priority: P2)

A user asks a general money-knowledge question ("How big should an emergency fund
be?", "What's the difference between APR and APY?") and receives an explanatory
answer drawn from a curated financial-literacy library, with citations to the
sources used. If nothing relevant exists in the library, the system says so rather
than inventing an answer.

**Why this priority**: This is the knowledge layer that lets the agent give helpful
guidance beyond the user's raw numbers. It depends on the chat surface (US1) but
delivers distinct value. The citation and no-answer behaviors are the trust
guarantees that make the guidance safe to show.

**Independent Test**: Ask a question that the curated library covers and confirm
the answer carries at least one citation traceable to a source document; ask a
question clearly outside the library's scope and confirm the system returns an
honest "I don't have guidance on that" rather than a fabricated answer.

**Acceptance Scenarios**:

1. **Given** a knowledge question covered by the library, **When** the user asks
   it, **Then** the answer is grounded in retrieved passages and displays one or
   more citations identifying the source.
2. **Given** a knowledge question with no relevant material in the library, **When**
   the user asks it, **Then** the system returns a no-answer response that admits it
   lacks the information, and presents no invented facts or citations.
3. **Given** a knowledge answer, **When** it is shown, **Then** it contains no
   personal financial figures presented as retrieved facts (numbers about the user
   come only from their data).

---

### User Story 3 - Ask a complex, multi-step money question (Priority: P2)

A user asks a question that cannot be answered by a single lookup — for example
"Can I afford a £1,200 holiday in August without missing my savings goal?" The
agent reasons across several steps: it checks recent spending and the balance
forecast, weighs the user's goals, retrieves relevant guidance, and returns one
coherent answer that reconciles all of them, with citations for the guidance
portion.

**Why this priority**: This is the flagship capability that differentiates the
agent from a lookup tool — genuine multi-source reasoning. It depends on US1
(exact data tools) and US2 (knowledge retrieval) but is the headline demo of the
phase.

**Independent Test**: Run the affordability question against a seeded account and
confirm the single answer visibly draws on the user's transactions, their balance
forecast, their goal(s), and cited knowledge — not just one of these.

**Acceptance Scenarios**:

1. **Given** a user with transaction history, a balance forecast, and at least one
   savings goal, **When** they ask whether they can afford a specific future
   purchase, **Then** the answer reflects all of: recent and projected balance, the
   purchase amount, the goal, and relevant cited guidance — in one response.
2. **Given** a multi-step question, **When** the agent works on it, **Then** its
   reasoning is bounded — it stops after a capped number of steps and a capped
   amount of work rather than looping indefinitely.
3. **Given** a step in the agent's reasoning fails (a tool errors), **When** it
   happens, **Then** the user still receives a coherent, readable answer or a clear
   apology, never a raw error or a stack trace.

---

### User Story 4 - Track goals and have the agent remember context (Priority: P3)

A user tells the agent about a financial goal ("I want to save £5,000 for a car by
next June") and later refers back to it ("Am I on track?"); within a conversation
the agent remembers what was already discussed, and durable preferences the user
asks it to remember persist across sessions.

**Why this priority**: Goals and memory make the agent feel continuous and
personal, but the core question-answering loop delivers value without them, so they
come after the answering capabilities.

**Independent Test**: Set a goal through chat, confirm it is stored and retrievable;
in the same conversation refer back to an earlier message and confirm the agent
uses that context; ask the agent to remember a durable preference and confirm it is
recorded with an audit trail and is recalled in a later session.

**Acceptance Scenarios**:

1. **Given** a user states a goal in chat, **When** the agent records it, **Then**
   the goal is saved to the user's goals and can be listed and referenced later.
2. **Given** an ongoing conversation, **When** the user refers to something said
   earlier in the same session, **Then** the agent has that short-term context
   available without the user repeating it.
3. **Given** the user asks the agent to durably remember a preference, **When** it
   does, **Then** the memory is written only through the explicit remember action,
   the write is recorded in an audit trail, and the memory is scoped to that user
   and recalled only for that user.
4. **Given** short-term conversation context, **When** a justified period of
   inactivity passes, **Then** that short-term context expires, while durable goals
   and durable memories remain.

---

### User Story 5 - Make changes by talking to the agent (Priority: P3)

A user asks the agent to record a one-off transaction ("Add a £40 cash payment to
the plumber yesterday") or to correct a category ("That Amazon charge was
groceries, not shopping"), and the agent performs the change safely — validating
the input, scoping it to the user, and refusing abusive volumes of writes.

**Why this priority**: Conversational writes are a convenience that reuses existing
data paths; they are valuable but secondary to reading and reasoning, and they
carry the most risk, so they are gated last.

**Independent Test**: Ask the agent to add a transaction and confirm it appears in
the user's data; ask it to reclassify a transaction and confirm the change is
recorded with the correct provenance; attempt rapid repeated writes and confirm the
system limits them.

**Acceptance Scenarios**:

1. **Given** a user asks the agent to add a transaction, **When** the request has
   the needed details, **Then** the transaction is added to that user's data and
   confirmed back to them.
2. **Given** a user asks the agent to reclassify a transaction's category, **When**
   the agent applies it, **Then** the change is recorded as a human-originated
   correction scoped to that user.
3. **Given** a write request with missing or invalid details, **When** the agent
   evaluates it, **Then** the write is rejected with a readable explanation and no
   partial change is made.
4. **Given** a burst of write requests beyond a reasonable rate, **When** they
   arrive, **Then** the system throttles them and tells the user rather than
   executing all of them.

---

### Edge Cases

- **Ambiguous question**: when a turn could be enumerable or open-ended, it is
  routed to the reasoning agent rather than answered with a possibly-wrong template;
  the share of turns handled without the agent is measured and reported.
- **Empty knowledge retrieval**: a knowledge question that retrieves nothing
  relevant yields a no-answer, never an invented one (see US2).
- **No personal data yet**: a brand-new user asking about their balance gets a clear
  "no data yet, upload a statement" style answer, not a fabricated figure or error.
- **Tool failure mid-reasoning**: a failing tool returns a structured error the
  agent can handle; the user never sees a raw error or stack trace.
- **Prompt-injection / off-domain input**: the chat path passes through input and
  output checkpoints (no-op in this phase, real logic in the security phase) so the
  wiring exists before the rules do; behavior in this phase is unchanged but the
  hook points and a redaction call site are present.
- **Cross-user leakage attempt**: every tool runs under the asking user's access
  scope; one user can never retrieve another user's transactions, goals, or
  memories, even by asking the agent directly.
- **Runaway reasoning**: the agent is capped on number of steps and total work; on
  reaching a cap it returns its best bounded answer instead of continuing.
- **Numeric question phrased as knowledge** ("typically, how much is my rent?"): the
  personal figure still comes from exact data, not from the knowledge library.

## Requirements *(mandatory)*

### Functional Requirements

#### Chat surface & routing

- **FR-001**: The system MUST provide a chat interface, available only to signed-in
  users, where a user can ask money questions in plain language and receive answers.
- **FR-002**: The system MUST stream responses incrementally rather than only
  presenting a completed answer.
- **FR-003**: The system MUST route each turn through a deterministic classifier
  that answers enumerable turns (at minimum: current balance, subscriptions list,
  and simple single-category totals) with an exact query and a fixed response
  template, without invoking the reasoning agent.
- **FR-004**: The system MUST send ambiguous or multi-step turns to the reasoning
  agent rather than forcing them through a template.
- **FR-005**: The system MUST measure and record the proportion of turns resolved by
  the deterministic router versus the reasoning agent.

#### Bounded agent & tools

- **FR-006**: The reasoning agent MUST operate as a single bounded loop capped at 8
  tool-calling iterations and a ~16k-token total budget per turn, and MUST return its
  best bounded answer when either cap is reached.
- **FR-007**: The agent MUST only use tools from an explicit allowlist; no tool
  outside the allowlist can be invoked. The allowlist for this phase is: query the
  user's transactions, get the balance forecast, get anomalies, get subscriptions,
  run an affordability check, run a what-if scenario, search the financial-knowledge
  library, list goals, set a goal, remember a durable memory, add a transaction, and
  reclassify a transaction.
- **FR-008**: Every tool input MUST be validated against a defined schema before the
  tool runs; invalid input is rejected without executing the tool.
- **FR-009**: Every tool MUST execute under the asking user's data-access scope, so
  that no tool can read or write another user's data.
- **FR-010**: A tool failure MUST return a structured error the agent can reason
  about; the user MUST never be shown a raw error or stack trace.

#### Grounding & knowledge (RAG)

- **FR-011**: Personal financial figures in any answer MUST be derived from exact
  queries over the user's own data, never from retrieved knowledge text.
- **FR-012**: The system MUST answer financial-literacy questions by retrieving from
  a curated, openly-licensed shared knowledge library that is not filtered per user.
- **FR-013**: Every answer grounded in the knowledge library MUST display citations
  identifying the source passages used.
- **FR-014**: When retrieval finds nothing relevant to a knowledge question, the
  system MUST return a no-answer that admits the gap and MUST NOT fabricate facts or
  citations.
- **FR-015**: Each retrieval enhancement beyond baseline retrieval (e.g., reranking,
  query rewriting, metadata filtering) MUST be justified by a measured improvement
  on the knowledge golden set; an enhancement that does not measurably help MUST be
  cut, and the measurement MUST be recorded.

#### Goals & memory

- **FR-016**: Users MUST be able to create, list, and update financial goals, both
  through chat and as stored records. A goal MUST carry a name, a target amount, and a
  target date, and a status of active, achieved, or abandoned.
- **FR-017**: The system MUST retain short-term conversation context for the
  duration of an active session and expire it after 30 minutes of inactivity, while
  durable goals and memories persist.
- **FR-018**: Durable long-term memories MUST be written only through an explicit
  remember action, MUST be scoped to the writing user, and MUST be retrievable only
  for that user.
- **FR-019**: Every durable-memory write MUST create an audit record capturing that
  the write occurred.

#### Conversational writes

- **FR-020**: Agent-performed writes (add a transaction, set a goal, reclassify a
  transaction, remember a memory) MUST be schema-validated, scoped to the user, and
  rate-limited to 10 writes per minute per user; writes beyond that rate MUST be
  throttled with a readable message.
- **FR-021**: A reclassification performed via the agent MUST be recorded with
  human-originated provenance (it reflects a user's explicit instruction).

#### Safety wiring & operations

- **FR-022**: The chat path MUST include input and output checkpoints and a
  redaction call site that are present but inert in this phase (no-op), so the
  security phase can fill in real logic without re-plumbing the chat path.
- **FR-023**: All prompts used by the system MUST live as version-controlled files
  in the dedicated prompts location, never as inline strings in code.
- **FR-024**: All answers MUST be scoped to the asking user; no answer may include
  another user's data.
- **FR-025**: The system MUST record evaluation results for tool selection and for
  knowledge retrieval as committed quality gates with real measured numbers.

### Key Entities *(include if feature involves data)*

- **Conversation / Turn**: a chat session belonging to one user, made of ordered
  turns (a user message and the system's answer), with short-term context that lives
  only for the active session. The conversation is ephemeral — it is not persisted as
  a browsable transcript and expires with the session; durable value is captured only
  as goals and explicit memories.
- **Knowledge Document & Passage**: a source in the curated financial-literacy
  library and the heading-aware passages it is split into; passages are the unit of
  retrieval and the target of citations. Shared across all users.
- **Citation**: a reference from an answer to the knowledge passage(s) that grounded
  it.
- **Goal**: a user's financial objective owned by one user — a name, a target amount,
  and a target date, with a status of active, achieved, or abandoned; listable and
  updatable.
- **Memory**: a durable, user-scoped fact or preference the user asked the agent to
  remember, each with an audit record of its creation.
- **Tool**: an allowlisted capability the agent may invoke, each with a defined
  input schema and an output, executed under the caller's access scope.
- **Router decision**: the record of whether a turn was handled deterministically or
  by the agent, used to measure router coverage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every enumerable question (balance, subscriptions, simple category
  total), the answer matches the figure computed directly from the user's data in
  100% of test cases.
- **SC-002**: The tool-selection golden set (~15 representative cases) passes its
  committed threshold with real measured numbers, and the result blocks merge on
  regression.
- **SC-003**: The knowledge-retrieval golden set (~15 question/passage triples)
  reports hit@5, mean reciprocal rank, and faithfulness, each meeting its committed
  threshold with real measured numbers and, where a human-judged metric is used, a
  reported agreement rate against hand labels.
- **SC-004**: Every answer that draws on the knowledge library shows at least one
  citation; in a test set of off-library questions, 100% produce a no-answer rather
  than a fabricated answer.
- **SC-005**: The affordability question produces a single answer that demonstrably
  incorporates the user's transactions, their forecast, their goal(s), and cited
  guidance together.
- **SC-006**: The proportion of turns resolved without the reasoning agent is
  measured and reported, demonstrating the deterministic router carries the
  enumerable load.
- **SC-007**: No answer in any test ever exposes another user's data, and no
  personal figure is ever sourced from retrieved knowledge text.
- **SC-008**: The reasoning agent always terminates within its caps (≤ 8 tool-calling
  iterations and ≤ ~16k tokens per turn); no test turn runs unbounded.
- **SC-009**: Users perceive responses as immediate — streamed output begins
  promptly rather than after the full answer is composed.
- **SC-010**: Every durable-memory write in testing has a corresponding audit
  record; no durable memory is created by any path other than the explicit remember
  action.

## Assumptions

- **Authentication reuse**: sign-in, sessions, and per-user data isolation from the
  earlier phases are reused as-is; this phase adds the chat surface, router, agent,
  RAG, goals, and memory on top.
- **Exact-data tools wrap existing services**: the read tools (transactions,
  forecast, anomalies, subscriptions) and the write paths (add transaction,
  reclassify) consume the already-shipped ingestion and analytics capabilities; this
  phase exposes them as agent tools rather than reimplementing them.
- **Knowledge corpus**: the curated library is openly-licensed financial-literacy
  material (consumer-finance / money-guidance class) plus the project's own
  explainers, assembled in this phase; it is shared and identical for all users.
- **Short-term memory horizon**: short-term conversation context is session-scoped and
  expires after 30 minutes of inactivity (resolved in clarification); durable goals and
  memories are unaffected.
- **Write rate limits**: agent-performed writes are capped at 10 per minute per user
  (resolved in clarification).
- **Language scope**: the chat operates in English for this phase, consistent with
  the existing knowledge material and UI.
- **Rails are inert here**: the input/output checkpoints and redaction site are
  scaffolding only in this phase; real guardrail logic, red-teaming, and the review
  queue/lifecycle belong to later phases and are explicitly out of scope.
- **Model roles**: a lighter model handles mechanical steps (routing / rewriting)
  and a stronger model handles synthesis, with a failover provider behind a single
  adapter; this is an existing capability reused here.
