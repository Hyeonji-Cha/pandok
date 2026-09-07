# Synthetic Gateway → AWS E2E

## Fully local test (safe; no AWS account required)

From this directory:

```bash
python synthetic_gateway_to_aws_e2e.py
```

Expected output:

```text
PASS: synthetic Gateway -> AWS HTTP E2E; 2 transient AWS failures retried; 5 v2 events accepted; client retry deduped
```

The script uses only localhost, synthetic credentials, a temporary SQLite file, the packaged v2 schema reference, and the five sanitized example events. It deliberately makes the mock AWS receiver return two 503 responses to exercise retry handling.

## Real AWS test-destination E2E after deployment

Use a dedicated non-production AWS ingest endpoint and test server-to-server credential. Configure the Gateway with `PANDOK_AWS_EXPORT_ENABLED=1`, the test endpoint, and the credential file path. Send `examples/complete_run_sequence.jsonl` one event at a time using `CONTROLLED_SCENARIO` and the controlled-test inbound token. Verify:

1. Gateway returns HTTP 204 for all five events.
2. AWS test destination records exactly five unique `event_id` values.
3. AWS body for each event equals the validated v2 JSON body.
4. Re-send the final event; Gateway should return 204 and the AWS unique count should remain five.
5. Temporarily make the test destination return 503 and verify retry/recovery; if failures exceed the retry budget the Gateway returns 503 with `Retry-After: 1` and does not commit local aggregation/dedupe for that failed export.
6. Verify no access logs or application logs contain IP, Authorization, payload body, `run_id`, or request timestamps.

Do not use production player data for this test.
