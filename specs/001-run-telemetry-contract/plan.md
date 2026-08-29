# Implementation Plan: Run Telemetry Contract

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-run-telemetry-contract/spec.md`

## Summary

Create a versioned, executable contract for the six P0 King Charles telemetry events. The first slice
uses strict JSON Schema for individual-event validation and a small Python package for privacy checks
and cross-event Run-sequence invariants. Accepted and rejected fixtures plus automated tests make the
contract usable before the game integration build exists.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `jsonschema` 4.x for Draft 2020-12 validation; standard library for CLI and
sequence checks

**Storage**: Versioned JSON Schema and JSON fixture files in Git; no runtime database

**Testing**: pytest 8.x with schema, privacy, fixture, and sequence contract tests

**Target Platform**: Windows developer workstation and Linux CI/runtime

**Project Type**: Python library with a command-line validation entry point

**Performance Goals**: Validate 10,000 representative events in under 10 seconds on a developer
workstation; P0 correctness is prioritized over throughput tuning

**Constraints**: No AWS credentials or live game build required; deterministic offline tests; strict
rejection of direct-identifier fields; developer-pending gameplay values remain optional

**Scale/Scope**: Six P0 event types, one complete valid Run sequence, and focused invalid fixtures for
each contract rule

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| Consent and Data Minimization | Contract excludes direct identifiers and validates consent boundary assumptions | PASS |
| Contract-First Telemetry | Versioned schema and fixtures precede ingestion implementation | PASS |
| One Copy, Multiple Engines | This slice is storage-neutral and introduces no analytical copy | PASS |
| Verifiable and Recoverable Data | Stable `event_id`, duplicate semantics, rejection reasons, and monotonic checks are testable | PASS |
| Cost-Aware, Reproducible Operations | Validation is local and offline; no cloud resources or spend | PASS |

**Post-design re-check**: PASS. The data model and interface contract preserve all five principles;
there are no justified exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/001-run-telemetry-contract/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── telemetry-events-v1.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
contracts/
└── telemetry-event-v1.schema.json

src/pandok_contracts/
├── __init__.py
├── cli.py
├── errors.py
└── validator.py

tests/
├── contract/
│   ├── fixtures/
│   │   ├── valid/
│   │   └── invalid/
│   ├── test_event_contract.py
│   ├── test_privacy_rules.py
│   └── test_run_sequence.py
└── conftest.py

pyproject.toml
README.md
```

**Structure Decision**: Use one small installable Python package so the same validator can run locally,
in CI, and later inside the ingestion boundary. Keep the executable schema at the repository root as
the single contract source; feature documentation explains rather than duplicates it.

## Complexity Tracking

No constitution violations or complexity exceptions are required.
