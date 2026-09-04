# Privacy / logging confirmation

## Code-level confirmation for this release candidate

- The v2 contract contains no `anonymous_user_id`, `session_id`, client `event_time`, device ID, network identity, or player-account identifier.
- The Gateway recursively rejects known privacy/network identity field names before contract validation.
- The outbound AWS body is the already validated v2 payload; request metadata is not merged into it.
- The exporter does not read `request.client`, forwarded IP headers, access-log records, or request-arrival timestamps.
- `run_id` is never generated or transformed by the Gateway; it is preserved from the validated Unity payload.
- The Gateway does not map IP addresses, request timestamps, authentication values, or player-identifying information into `run_id`.
- Raw event payloads are not written to SQLite. The local dedupe table stores HMAC-SHA256(event_id) plus expiry, not raw event IDs.
- The application source contains no `logging` or `print` calls that emit request payloads or credentials.
- The production systemd command previously observed uses Uvicorn `--no-access-log`; the post-deploy verification script checks that this remains true.

## Deployment status

These are properties of the release candidate code. Do not describe them as a deployed-production confirmation until `post_deploy_capture.sh` has been run successfully against the actual deployed service.
