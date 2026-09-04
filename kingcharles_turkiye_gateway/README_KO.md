# King Charles Türkiye Gateway Handoff

> 이 폴더는 **King Charles Türkiye Privacy Gateway → PANDOK AWS v2** 연동 전용 작업 공간입니다.

## Authoritative contract

AWS-bound primary contract는 저장소 루트의 다음 파일 하나입니다.

`contracts/telemetry-event-v2.schema.json`

`aggregate-export-v1`은 **optional secondary/reconciliation output**으로만 유지합니다.

## Target flow

```text
King Charles Unity
  -> Türkiye Privacy Gateway
  -> telemetry-event-v2 validation
  -> privacy-field rejection
  -> event deduplication
  -> server-to-server AWS export
  -> AWS API Gateway / validation / downstream
```

AWS-bound v2 payload에는 persistent player/session identity, client IP/network field,
client wall-clock timestamp가 없어야 합니다. `run_id`는 한 Run 내부 연결에만 사용하며
player identity에 매핑하지 않습니다.

## Main implementation

- `gateway_export/app_phase2_8.py` — deployable v2 Gateway + AWS export entry point
- `gateway_export/sync_exact_contract.py` — canonical contract pin/verification
- `gateway_export/deploy_v2_aws_export.sh` — server deployment
- `gateway_export/synthetic_gateway_to_aws_e2e.py` — synthetic E2E
- `tests/test_gateway_v2.py`
- `tests/test_gateway_v2_export.py`
- `examples/` — all five v2 event examples + complete Run sequence

## Do not commit

- production credentials / tokens / AWS keys
- real production endpoints or server IPs
- `.env` secrets
- SSH/TLS private keys
- real player telemetry or production logs
- actual SQLite/database files

## Deployment status

Repository code is a release candidate until the server deployment and real synthetic
Gateway-to-AWS test are completed. After deployment, capture the deployed file hashes/version
with `gateway_export/post_deploy_capture.sh`.
