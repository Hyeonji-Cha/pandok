# 02. Data Engineer 작업 가이드

## Primary input

Data Engineer가 primary AWS-bound input으로 받아야 하는 것은
`contracts/telemetry-event-v2.schema.json`에 맞는 sanitized Run-level v2 event입니다.

`aggregate-export-v1`은 optional secondary/reconciliation output입니다.

## Local test

Repo root에서:

```powershell
python -m pip install -r .\kingcharles_turkiye_gateway\gateway_export\requirements-v2.txt
python .\kingcharles_turkiye_gateway\tests\test_gateway_v2.py
python .\kingcharles_turkiye_gateway\tests\test_gateway_v2_export.py
python .\kingcharles_turkiye_gateway\gateway_export\synthetic_gateway_to_aws_e2e.py
```

Expected: all PASS.

## AWS interface

Unity는 AWS credential을 받지 않습니다.
Türkiye Gateway가 server-to-server credential을 server-side file/config에서 읽고 AWS 요청을 만듭니다.

## Data rules

AWS-bound v2 event에 다음을 추가하지 않습니다:
- player/user/session persistent identifier
- IP/network field
- client wall-clock timestamp
- credential
- raw log/body metadata

`run_id`는 한 Run 내 event linkage용이며 player identity lookup key가 아닙니다.
