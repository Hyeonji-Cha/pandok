# Research: Run Telemetry Contract

## Decision 1: Contract Representation

**Decision**: Use JSON Schema Draft 2020-12 with one strict branch per P0 event name.

**Rationale**: It is language-neutral, reviewable by the game developer, executable in tests, and able
to express required fields, numeric ranges, enums, UUIDs, and timestamps. Strict per-event branches
also prevent unknown or privacy-sensitive fields from passing unnoticed.

**Alternatives considered**:

- Protobuf: compact and strongly typed, but adds code generation and is less convenient for the
  game's initial HTTP JSON integration.
- Avro: appropriate for streaming serialization, but less direct as the developer-facing HTTP
  contract and weaker for human-reviewed examples.
- Documentation-only examples: easy to write but cannot prevent contract drift.

## Decision 2: Flat Event Shape

**Decision**: Retain the agreed flat event shape with common fields beside event-specific fields.

**Rationale**: It matches the examples already shared with the developer and keeps test payloads easy
to inspect. Replacing it with an envelope and nested payload now would create coordination cost without
a demonstrated need.

**Alternatives considered**:

- Common envelope plus nested payload: cleaner separation but would change the agreed examples.
- Separate endpoint per event: unnecessary coupling and duplicated client logic.

## Decision 3: Cross-Event Validation

**Decision**: Apply schema validation to individual events and a Python sequence validator to
relationships across a Run.

**Rationale**: JSON Schema validates one document at a time; it cannot prove that a selection refers to
previously shown options or that cumulative counters are monotonic. Keeping these checks separate makes
failure reasons explicit and testable.

**Alternatives considered**:

- Schema-only validation: cannot enforce Run-level invariants.
- Streaming engine validation first: would require cloud resources and delay the independent slice.

## Decision 4: Developer-Pending Fields

**Decision**: Make game-state fields whose code availability is unconfirmed optional in contract v1,
while requiring their types and ranges whenever present.

**Rationale**: This allows the developer to integrate the stable event lifecycle first without
fabricating unavailable values. Once access is confirmed, a compatible minor contract update may make
specific fields required for production readiness.

**Alternatives considered**:

- Require every proposed field immediately: risks blocking the first build or encouraging dummy data.
- Remove the fields: loses the intended analytical design and review context.

## Decision 5: Python Tooling

**Decision**: Use Python 3.12, `jsonschema`, pytest, and a minimal standard-library CLI.

**Rationale**: The tooling is cross-platform, familiar in data engineering, lightweight, and reusable
later in ingestion tests. A `src` package layout prevents tests from accidentally importing the working
directory instead of the installed package.

**Alternatives considered**:

- Node.js validator: equally viable but adds a second ecosystem before dashboard work begins.
- Custom validation without a schema library: increases defect risk and obscures the standard contract.

## Decision 6: Privacy Rule Enforcement

**Decision**: Combine strict schemas with a recursive deny-list check for prohibited identifier keys.

**Rationale**: Strict fields prevent accidental additions to known events, while recursive scanning
produces a clear privacy-specific error if a prohibited key appears inside nested options or upgrades.

**Alternatives considered**:

- Strict schema only: rejects the event but may not clearly explain the privacy violation.
- Value-based PII detection: unreliable, prone to false positives, and outside P0 scope.
