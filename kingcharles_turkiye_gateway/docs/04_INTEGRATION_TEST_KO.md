# 04. 통합 테스트 가이드

Minimum acceptance coverage:

1. All five v2 event examples validate against `contracts/telemetry-event-v2.schema.json`.
2. `session_started` fails.
3. user/session identifiers fail.
4. IP/network fields fail.
5. client wall-clock timestamp fields fail.
6. duplicate event submission is exported/aggregated only once.
7. transient AWS/network errors retry using the defined retry budget.
8. permanent 4xx export errors are not retried indefinitely.
9. failure handling does not dump raw payloads or credentials.
10. implementation contains no client-IP/raw-body logging path.
11. one complete synthetic Run reaches the synthetic AWS receiver.
12. forbidden-field request is rejected before export.

Run:

```powershell
python .\kingcharles_turkiye_gateway\tests\test_gateway_v2.py
python .\kingcharles_turkiye_gateway\tests\test_gateway_v2_export.py
python .\kingcharles_turkiye_gateway\gateway_export\synthetic_gateway_to_aws_e2e.py
```
