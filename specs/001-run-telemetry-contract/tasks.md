# Tasks: Run Telemetry Contract

**Input**: Design documents from `specs/001-run-telemetry-contract/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Contract and sequence tests are required by FR-015 and the project constitution.

**Organization**: Tasks are grouped by user story so each story remains independently testable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the cross-platform Python project and test layout.

- [x] T001 Create Python 3.12 project metadata, runtime dependency, test dependency, and CLI entry point in `pyproject.toml`
- [x] T002 [P] Create package exports in `src/pandok_contracts/__init__.py`
- [x] T003 [P] Add Python, virtual-environment, test-cache, and local-secret exclusions in `.gitignore`
- [x] T004 [P] Add shared repository and fixture path helpers in `tests/conftest.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared errors and contract primitives used by every story.

**Critical**: No user story implementation begins until this phase is complete.

- [x] T005 Create stable validation reason codes and structured error result types in `src/pandok_contracts/errors.py`
- [x] T006 Define common event, upgrade option, and upgrade state definitions in `contracts/telemetry-event-v1.schema.json`
- [x] T007 Create representative common-field fixture values in `tests/contract/fixtures/valid/p0_run_sequence.json`

**Checkpoint**: The project installs, imports, and has one reviewable P0 event-sequence fixture.

---

## Phase 3: User Story 1 - Validate the P0 Run Flow (Priority: P1) MVP

**Goal**: Validate all six P0 event shapes plus their Run-level relationships and monotonic counters.

**Independent Test**: The complete valid P0 Run fixture passes schema and sequence validation with no
manual correction.

### Tests for User Story 1

- [x] T008 [P] [US1] Add schema acceptance tests for all six P0 events in `tests/contract/test_event_contract.py`
- [x] T009 [P] [US1] Add choice-link, correlation, duplicate, and monotonic sequence tests in `tests/contract/test_run_sequence.py`

### Implementation for User Story 1

- [x] T010 [US1] Add strict per-event branches for all six P0 events in `contracts/telemetry-event-v1.schema.json`
- [x] T011 [US1] Implement schema loading and single-event validation in `src/pandok_contracts/validator.py`
- [x] T012 [US1] Implement Run-sequence relationship, duplicate, and monotonic checks in `src/pandok_contracts/validator.py`
- [x] T013 [US1] Implement `validate-event` and `validate-sequence` commands in `src/pandok_contracts/cli.py`

**Checkpoint**: User Story 1 passes independently and provides the developer-independent MVP.

---

## Phase 4: User Story 2 - Reject Unsafe or Malformed Events (Priority: P2)

**Goal**: Return specific failures for malformed, conflicting, and privacy-violating telemetry.

**Independent Test**: Every invalid fixture is rejected with its expected stable reason code.

### Tests for User Story 2

- [x] T014 [P] [US2] Add malformed-field and range rejection fixtures under `tests/contract/fixtures/invalid/`
- [x] T015 [P] [US2] Add recursive prohibited-key fixtures and privacy tests in `tests/contract/test_privacy_rules.py`
- [x] T016 [P] [US2] Add duplicate-conflict tests in `tests/contract/test_run_sequence.py`

### Implementation for User Story 2

- [x] T017 [US2] Implement recursive prohibited-key detection and stable privacy failures in `src/pandok_contracts/validator.py`
- [x] T018 [US2] Normalize schema and sequence failures into structured CLI output in `src/pandok_contracts/cli.py`

**Checkpoint**: Unsafe data is distinguishable from valid telemetry before any cloud ingestion exists.

---

## Phase 5: User Story 3 - Evolve the Contract Safely (Priority: P3)

**Goal**: Make versioning, optional developer-pending fields, and compatibility behavior clear.

**Independent Test**: A fixture omitting developer-pending fields remains valid, while an unsupported
schema version and unknown field are rejected.

### Tests for User Story 3

- [x] T019 [P] [US3] Add optional-field and incompatible-version tests in `tests/contract/test_event_contract.py`

### Implementation for User Story 3

- [x] T020 [US3] Document supported events, field status, reason codes, and versioning in `README.md`
- [x] T021 [US3] Add developer-facing valid example commands and expected results to `README.md`

**Checkpoint**: The contract can be reviewed and used without relying on conversation history.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify portability, performance, and documentation accuracy.

- [x] T022 [P] Add a 10,000-event validation performance check in `tests/contract/test_performance.py`
- [x] T023 Run all commands in `specs/001-run-telemetry-contract/quickstart.md` and correct any mismatch
- [x] T024 Run `python -m pytest`, schema self-validation, and `git diff --check`; record results in `README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 has no dependencies.
- Phase 2 depends on Phase 1 and blocks all user stories.
- User Story 1 depends on Phase 2 and is the MVP.
- User Stories 2 and 3 depend on Phase 2; both integrate with the validator established by User Story 1.
- Polish depends on all selected user stories.

### User Story Dependencies

- **US1**: Starts after Phase 2 and provides complete positive-flow validation.
- **US2**: Starts after Phase 2; its tests can be written in parallel, but implementation extends US1's validator.
- **US3**: Starts after Phase 2 and can be documented in parallel once schema field status is stable.

### Parallel Opportunities

- T002, T003, and T004 touch separate files.
- T008 and T009 are independent failing-test tasks.
- T014, T015, and T016 cover independent rejection categories.
- T019 and README drafting can proceed while US2 implementation is underway.

## Parallel Example: User Story 1

```text
Task: "Add schema acceptance tests in tests/contract/test_event_contract.py"
Task: "Add sequence invariant tests in tests/contract/test_run_sequence.py"
```

## Implementation Strategy

### MVP First

1. Complete setup and foundational tasks.
2. Write and observe failing US1 tests.
3. Implement the schema, validator, and CLI.
4. Stop and validate the complete P0 Run sequence before adding rejection refinements.

### Incremental Delivery

1. US1 proves the valid Run lifecycle.
2. US2 proves quarantine-worthy failure behavior and privacy enforcement.
3. US3 makes the boundary safe to share with the game developer.
4. Polish verifies Windows-oriented instructions and repeatability.

## Notes

- `[P]` tasks operate on separate files or independent tests.
- Tests MUST be written and observed failing before the related implementation task.
- Developer-pending game facts remain optional and MUST NOT be fabricated in production events.

## Phase 7: Convergence

- [x] T025 Enforce 60-second checkpoint cadence and increasing choice/checkpoint sequences with tests in `tests/contract/test_run_sequence.py` and logic in `src/pandok_contracts/validator.py` per FR-006 and plan data-model invariants (partial)
- [x] T026 Add parameterized rejection coverage for every required field plus malformed timestamps, UUIDs, ranges, event names, and versions in `tests/contract/test_event_contract.py` per FR-011, FR-015, and SC-002 (partial)
- [x] T027 Add recursive rejection coverage for every documented prohibited identifier key in `tests/contract/test_privacy_rules.py` per FR-010, FR-015, and SC-002 (partial)
- [x] T028 Re-run the full suite, schema self-validation, CLI quickstart, and Git checks and update verified totals in `README.md` per SC-001 through SC-003 (partial)
