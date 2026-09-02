# 03. Privacy Boundary

## Goal

AWS에서 접근 가능한 v2 data만으로 player/account/device/network identity를 식별하거나
여러 Run을 같은 사람에게 연결할 수 없어야 합니다.

## Authoritative v2 design

Removed from AWS-bound payload:
- `session_started`
- `anonymous_user_id`
- `session_id`
- client wall-clock `event_time`
- IP/network fields
- Steam/player/account/device identifiers

Allowed Run-only linkage:
- fresh random `run_id` per Run
- random `event_id`
- `event_sequence`
- `run_elapsed_seconds`

## Gateway enforcement

Gateway recursively rejects known privacy-sensitive key names before schema validation/export.
Canonical v2 schema also uses `unevaluatedProperties: false`, so unexpected payload fields fail validation.

## Logging

The v2 Gateway implementation does not read `request.client`, does not enable Uvicorn access logs in the
deployment service command, and does not log raw request bodies or credentials.

## Run linkage

No table or mapping in the v2 exporter maps `run_id` to user/session/player/IP identity.
