# 00. 현재 상태

## Primary direction

`contracts/telemetry-event-v2.schema.json`이 Türkiye Gateway → AWS의 authoritative contract입니다.
Sanitized Run-level v2 events가 primary AWS-bound path입니다.

`aggregate-export-v1`은 optional secondary/reconciliation output으로만 유지합니다.

## Implemented in this branch

- exact JSON Schema Draft 2020-12 validation
- five v2 events only:
  - `run_started`
  - `upgrade_options_shown`
  - `upgrade_selected`
  - `run_checkpoint`
  - `run_ended`
- `schema_version = "2.0"`
- privacy-field rejection before export
- HMAC-SHA256 event deduplication
- server-to-server export interface
- retry on transient AWS/network errors
- fail-closed handling for permanent export errors
- sanitized synthetic examples
- synthetic Gateway → mock-AWS HTTP E2E
- no raw request-body logging in implementation
- no `request.client` / client IP logging in implementation
- no player/session identity mapping to `run_id`

## Not yet claimed

Until actual server deployment is completed, this branch must not be described as the deployed v2 export.
Until the non-production AWS test destination receives the synthetic Run, real AWS E2E must not be marked PASS.

## Production rule

Never commit or publish real endpoints, credentials, player data, production logs, DB files, or server IPs.
