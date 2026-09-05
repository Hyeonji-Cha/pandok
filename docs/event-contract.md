# PANDOK v2 Telemetry Event Contract

The executable source of truth is
`contracts/telemetry-event-v2.schema.json`.

## Data Flow

```text
Unity
-> Türkiye Gateway
-> privacy removal, validation, and retry handling
-> PANDOK v2 Run events
-> AWS Sydney Bronze
-> Silver Run reconstruction
-> Gold aggregates
```

Unity must not send telemetry directly to AWS. The Türkiye Gateway rebuilds an
allow-listed payload and must not forward client IP headers or original request
bodies.

## Required Privacy Boundary

- Every Run receives a random `run_id` that is not mapped across Runs.
- Every logical event receives a random `event_id`; exact retries reuse it.
- `event_sequence` represents Run order.
- `run_elapsed_seconds` represents relative gameplay time.
- Player, account, Session, installation, device, network, and exact client-time
  fields are rejected.
- `session_started` is never sent to AWS.

## Processing Rules

- Bronze preserves each validated v2 event and adds AWS `received_at` metadata.
- Silver deduplicates retries and reconstructs Runs by `event_sequence`.
- Missing events remain `INCOMPLETE`; conflicting data becomes `INVALID`.
- Gold uses only valid or explicitly approved completeness states.
- `run_ended` may include the bounded `death_cause` only when `end_reason` is
  `player_death`; omission remains valid for older compatible clients.

`aggregate-export-v1` is an optional comparison contract and does not replace
the PANDOK v2 event flow.
