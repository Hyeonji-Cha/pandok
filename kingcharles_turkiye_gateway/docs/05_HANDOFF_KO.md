# 05. Game Developer -> Data Engineer Handoff

## Primary AWS-bound path

```text
Unity
 -> Türkiye Privacy Gateway
 -> exact telemetry-event-v2 validation
 -> privacy-field rejection
 -> event deduplication
 -> server-to-server AWS request
 -> AWS ingestion/downstream
```

`aggregate-export-v1` is optional secondary/reconciliation output only.

## Handoff evidence after deployment

Provide sanitized:
- deployed v2 export source snapshot
- deployed commit/hash/version identifier
- current Unity/Gateway -> v2 field mapping
- all five v2 examples + complete Run sequence
- validation/privacy/dedupe/retry/failure test results
- server-to-server auth interface with placeholders only
- privacy/logging/run-linkage confirmation
- synthetic Gateway-to-AWS E2E instructions/results

Never include real credentials, endpoint, IP, player data, production logs, or database files.
