# Telemetry Events v1 Interface Contract

## Boundary

This contract describes one JSON object per telemetry event. The game client may retry delivery, but
it must preserve the original `event_id`. Event order is not guaranteed at the receiving boundary.

The executable source of truth will be `contracts/telemetry-event-v1.schema.json`. This document
explains behavioral rules that require more than single-document schema validation.

## Supported Events

| Event | Run ID | Purpose |
|---|---:|---|
| `session_started` | Optional | Begin one consented application session |
| `run_started` | Required | Begin active gameplay for one Run |
| `upgrade_options_shown` | Required | Record both displayed upgrade options |
| `upgrade_selected` | Required | Record the player's linked selection |
| `run_checkpoint` | Required | Record cumulative Run state every 60 active seconds |
| `run_ended` | Required | Record the final available Run summary and end reason |

## Delivery Semantics

- Delivery is at least once: a valid event may be received more than once.
- An identical `event_id` and identical content is a retry duplicate.
- An identical `event_id` with different content is a conflict.
- Network arrival order is not a reliable gameplay order; use `event_time`, sequence fields, and
  identifiers when reconstructing a Run.
- A missing `run_ended` or `session_ended` does not prove the player is still active.

## Consent Boundary

- No event may be created or sent before explicit consent.
- Revocation stops new events and discards unsent queued events.
- Direct-identifying fields are forbidden at all nesting levels.

## Compatibility

- Additive optional fields may be introduced without invalidating existing v1 fixtures only after
  documentation and tests are updated.
- Removing a field, changing its meaning or type, or making an optional field required is incompatible
  and requires a new supported schema version or an explicitly managed migration.
- Localized display names are presentation data and must never replace stable identifiers.

## Cross-Event Validation Results

The sequence validator returns a non-zero result when any event is invalid or when a relationship or
monotonicity rule fails. Each failure identifies the event when possible and supplies a stable reason
code plus human-readable detail.
