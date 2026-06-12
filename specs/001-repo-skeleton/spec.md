# Feature Specification: Repository Skeleton & Project Map

**Feature Branch**: `001-repo-skeleton`

**Created**: 2026-06-12

**Status**: Draft

**Input**: User description: "briefs/phase-0-skeleton.md — Create the complete agreed folder tree with every file stubbed and carrying a header comment stating its single responsibility; the whole stack boots empty from a fresh clone."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh clone boots the whole stack empty (Priority: P1)

A developer clones the repository for the first time, copies the example
environment file to a working one, and starts the system with a single command.
Every default service comes up healthy with no business logic present — the
platform is an empty, running shell.

**Why this priority**: This is the foundational acceptance gate for the whole
project. If a fresh clone cannot boot, no later phase can be developed or
demonstrated. It is the single most valuable outcome of Phase 0.

**Independent Test**: From a clean machine, clone → copy example env to working
env → start the stack → confirm every default service reports healthy and the
model-serving stub answers its health check reporting "no model loaded" without
crashing.

**Acceptance Scenarios**:

1. **Given** a fresh clone with no prior state, **When** the developer copies the
   example environment file and starts the default stack, **Then** every default
   service (database, cache, object store, secrets store, migration runner,
   backend, model server, worker, frontend) reaches a healthy state.
2. **Given** the stack is running, **When** the model-serving stub is asked for
   its health, **Then** it responds successfully and reports "no model loaded"
   rather than crashing or refusing to boot.
3. **Given** the default startup command, **When** the stack starts, **Then** the
   heavy trainer service does NOT build or run (it is reserved for an opt-in
   training profile).
4. **Given** the migration runner service, **When** the stack starts, **Then** it
   applies the (empty) migration baseline and exits cleanly without holding the
   stack open.

---

### User Story 2 - Navigable project map from header comments (Priority: P2)

A developer (or the navigation/knowledge-graph tooling) needs to find where a
responsibility lives without reading implementation code. Every stub file opens
with a header comment that states, in one line, what that file is for. These
header comments form the project map.

**Why this priority**: The header-comment map is what makes the skeleton useful
as a foundation — it lets every later phase and the knowledge-graph tooling locate
the right file by responsibility. It depends on the tree existing (US1) but
delivers standalone navigation value.

**Independent Test**: Open any stub file across the tree and confirm its first
lines state its single responsibility; ask the navigation tooling where a known
concern (e.g., ingestion) lives and confirm it returns the correct path.

**Acceptance Scenarios**:

1. **Given** any stub file in the tree, **When** it is opened, **Then** its first
   lines are a header comment stating that file's single responsibility.
2. **Given** the knowledge-graph tooling has indexed the repository, **When** a
   developer asks where ingestion lives, **Then** the tooling returns the correct
   path.
3. **Given** the full agreed folder tree, **When** it is inspected, **Then** every
   required top-level area is present and empty of business logic.

---

### User Story 3 - Continuous integration is green on a clean checkout (Priority: P3)

A contributor opens a change and the automated checks run. On the empty skeleton,
the lint and type-check stages pass, establishing the green baseline that later
phases must keep.

**Why this priority**: A green CI baseline protects every later phase, but it is
only meaningful once the tree and stubs exist. It is the lowest-risk of the three
and can be added last.

**Independent Test**: Trigger the automated checks on a clean checkout and confirm
the lint and type-check stages complete successfully without depending on the
running stack.

**Acceptance Scenarios**:

1. **Given** the empty skeleton on a clean checkout, **When** CI runs, **Then**
   the lint and type-check stages pass.
2. **Given** the CI configuration, **When** it runs, **Then** it does not depend
   on the running application stack to pass.

---

### Edge Cases

- **Missing environment file**: If a developer starts the stack without first
  creating the working environment file from the example, startup fails with a
  clear, actionable message rather than a silent or cryptic failure.
- **Model-serving stub with no model present**: The model-serving stub must remain
  healthy and report "no model loaded"; the strict refuse-to-boot hash guard is
  explicitly out of scope for this phase and arrives later with the artifact it
  guards.
- **Accidental trainer build**: A plain default startup must never pull in the
  heavy trainer image; it is only built when the training profile is explicitly
  requested.
- **Inter-service addressing**: Services reference each other by service name, not
  by a local-loopback address, so the stack works unchanged inside the
  orchestrated network.
- **Ignored paths**: Generated and bulky directories (dependency caches, graph
  output, training data, virtual environments, build output) are excluded from
  both version control and knowledge-graph indexing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST contain the complete agreed folder tree covering
  the backend (core, api, services, repositories, domain, infra, workers, plus
  migrations, prompts, and unit/golden/redteam test areas), the model server, the
  trainer, the training notebooks area, the frontend (pages, components, api), the
  shared knowledge corpus, scripts, specs, docs, agent-config, and CI workflow
  areas.
- **FR-002**: Every stub file MUST begin with a header comment (a docstring for
  source files) that states the file's single responsibility in plain language.
- **FR-003**: The orchestration definition MUST declare all services — database
  with vector support, cache, object store, secrets store, a migration runner that
  applies migrations then exits, backend, model server, worker, frontend, and the
  trainer — with the trainer assigned to an opt-in training profile so it is
  excluded from default startup.
- **FR-004**: Services MUST address one another by service name and MUST NOT rely
  on local-loopback addressing.
- **FR-005**: The database, object store, and cache MUST use named persistent
  volumes so state survives restarts.
- **FR-006**: The repository MUST provide an example environment file; copying it
  to the working environment file MUST be sufficient configuration to boot the
  default stack.
- **FR-007**: The repository MUST include ignore rules for version control
  (including large-file-storage initialization) and a separate ignore list for the
  knowledge-graph tooling that excludes dependency caches, graph output, training
  data, virtual environments, and build output.
- **FR-008**: The repository MUST include a continuous-integration configuration
  whose lint and type-check stages pass on the empty skeleton and do not depend on
  the running stack.
- **FR-009**: The repository MUST include an evaluation-thresholds file at the
  repository root containing placeholder thresholds.
- **FR-010**: The model-serving stub MUST expose a health endpoint that responds
  successfully and reports "no model loaded" without crashing; it MUST NOT enforce
  any strict artifact/boot guard in this phase.
- **FR-011**: The knowledge-graph tooling MUST be installed scoped to this project
  and an initial graph MUST be generated from the skeleton.
- **FR-012**: The skeleton MUST contain NO business logic, authentication, data
  models, or real endpoints; only stubs and the minimum wiring needed for services
  to boot are in scope.
- **FR-013**: The migration runner MUST apply the (empty) migration baseline and
  exit cleanly without holding the rest of the stack open.

### Key Entities

- **Stub file**: A placeholder source or config file whose only content is a
  header comment declaring its single responsibility; the unit of the project map.
- **Service**: A named unit in the orchestration definition (database, cache,
  object store, secrets store, migration runner, backend, model server, worker,
  frontend, trainer) with a health state and, for stateful ones, a named volume.
- **Training profile**: The opt-in grouping under which the heavy trainer service
  lives so it is excluded from default startup.
- **Project map**: The collection of header comments across all stub files, used
  by humans and the knowledge-graph tooling to locate responsibilities by path.
- **Evaluation thresholds file**: A root-level file holding placeholder quality
  thresholds that later phases populate and CI gates against.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a fresh clone, a developer can bring the default stack to a
  fully healthy state with exactly two steps (create the working environment file,
  then start the stack) and no manual edits.
- **SC-002**: 100% of stub files begin with a header comment stating their single
  responsibility.
- **SC-003**: The default startup brings up every default service healthy and
  starts zero training-profile services.
- **SC-004**: The model-serving stub returns a healthy response reporting "no
  model loaded" on 100% of health checks while no model is present.
- **SC-005**: A navigation query for a known responsibility (e.g., "where does
  ingestion live") returns the correct path.
- **SC-006**: The lint and type-check stages of continuous integration pass on the
  empty skeleton without the running stack.
- **SC-007**: The full agreed folder tree is present, with every required
  top-level area accounted for and free of business logic.

## Assumptions

- The intended users of this phase are the project's developers and operators, not
  end users; "user value" here is a reliably bootable, navigable foundation.
- The fixed technology stack and authoritative documents named in the project's
  governing context apply; this phase does not choose or substitute technologies.
- A single-machine container runtime is the target environment for the boot
  acceptance test; multi-host orchestration is out of scope for this phase.
- Strict refuse-to-boot artifact guards are deliberately deferred to the later
  phases that introduce the artifacts they guard.
- The exact set of placeholder evaluation thresholds is not yet meaningful; any
  syntactically valid placeholder set that later phases can extend is acceptable.
- The knowledge-graph tooling is available to be installed project-scoped in the
  development environment.
