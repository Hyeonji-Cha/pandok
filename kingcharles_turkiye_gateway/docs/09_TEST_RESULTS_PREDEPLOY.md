# Pre-deployment test results

Date: 2026-09-02
Branch: gateway-v2-aws-export

## Canonical contract

Authoritative contract:

`contracts/telemetry-event-v2.schema.json`

Git blob SHA:

`4336417ea4107e4e9597ecddbcf989f38a240f7f`

Windows checkout may contain CRLF line endings. Gateway verification normalizes
CRLF to LF only for Git blob identity calculation. The schema content itself
is not rewritten or relaxed.

## Test 1 — Canonical v2 validation and aggregation

Command:

`python .\kingcharles_turkiye_gateway\tests\test_gateway_v2.py`

Result:

`PASS: canonical telemetry-event-v2 validation and v2 aggregation tests`

Status: PASS

## Test 2 — Privacy / dedupe / retry / failure handling / auth

Command:

`python .\kingcharles_turkiye_gateway\tests\test_gateway_v2_export.py`

Result:

`PASS: validation/privacy/dedupe/export retry/permanent failure/network failure/auth interface`

Verified:

- privacy-field rejection
- duplicate event suppression
- transient export retry
- permanent export failure handling
- network failure handling
- server-to-server auth interface
- no raw credential values in test output

Status: PASS

## Test 3 — Synthetic Gateway -> mock AWS HTTP E2E

Command:

`python .\kingcharles_turkiye_gateway\gateway_export\synthetic_gateway_to_aws_e2e.py`

Result:

`PASS: synthetic Gateway -> AWS HTTP E2E; 2 transient AWS failures retried; 5 v2 events accepted; client retry deduped`

Verified:

- all five v2 event types
- one complete synthetic Run
- two synthetic transient downstream failures
- retry behavior
- exactly five accepted downstream events
- duplicate client retry did not create duplicate downstream delivery

Status: PASS

## Security / repository checks

- `git diff --check`: no whitespace errors; Windows line-ending warnings only
- canonical root contract: unchanged
- secret scan: no production credential detected
- no production server IP detected
- localhost addresses are synthetic/local test endpoints only
- synthetic tokens are test-only values
- no production database file is included

## Still pending

The following must NOT yet be claimed as complete:

- deployment of this v2 export build to the Türkiye Gateway server
- deployed version/hash capture
- real non-production AWS ingestion E2E
- AWS-side receipt/downstream-shape confirmation

Those items will be completed after server deployment.
