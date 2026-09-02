# 01. 전체 작업 로드맵

## Phase 1 — Canonical contract

Authoritative contract:

`contracts/telemetry-event-v2.schema.json`

All Gateway validation, examples, tests, architecture, and handoff documentation must match it.

## Phase 2 — Repository implementation

Primary AWS-bound path:

```text
Unity -> Türkiye Gateway -> PANDOK v2 event -> AWS
```

`aggregate-export-v1` remains optional secondary/reconciliation output only.

## Phase 3 — Required tests

- all five v2 schemas PASS
- `session_started` rejected
- user/session identity fields rejected
- IP/network fields rejected
- client wall-clock timestamp fields rejected
- duplicate `event_id` does not create duplicate downstream delivery
- transient export failures retry
- permanent failures fail safely
- logs contain no raw payload, client IP, player identity, client timestamp, or credential
- `run_id` is not mapped to player identity

## Phase 4 — Deploy to Türkiye Gateway

Use `gateway_export/deploy_v2_aws_export.sh`.
Credentials and endpoint are configured only on the server, outside Git.

## Phase 5 — Synthetic Gateway → AWS E2E

Send only sanitized non-production v2 events.
Verify expected AWS ingestion receives exactly the v2 records.
Repeat with forbidden fields and verify rejection occurs before export.

## Phase 6 — Post-deploy evidence

Capture:
- deployed source snapshot
- deployed SHA-256 version identifiers
- test output
- auth interface with placeholders only
- privacy/logging confirmation
- synthetic E2E evidence

## Phase 7 — PR / review

Submit the dedicated branch through a pull request.
Do not merge production-sensitive material.
