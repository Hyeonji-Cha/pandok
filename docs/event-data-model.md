# Data Model: PANDOK v2 Run Telemetry

## Common Event Fields

| Field | Meaning | Validation |
|---|---|---|
| `event_id` | Logical event identity preserved across retries | Random UUID, required |
| `event_name` | P0 gameplay event category | One of five supported values |
| `event_sequence` | Gameplay order inside one Run | Positive integer |
| `run_elapsed_seconds` | Time elapsed from Run start | Non-negative number |
| `source_type` | Production, controlled, or load-test source | Required and consistent in one Run |
| `run_id` | Random identity for one Run only | UUID, required |
| `game_version` | Game build version | Non-empty string |
| `schema_version` | AWS event contract | `2.0` |

The contract does not accept player, account, installation, device, Session,
network identity, exact client timestamp, or free-form text fields.

## Event Types

- `upgrade_options_shown`: options actually displayed to the player
- `upgrade_selected`: selected option linked through `choice_id`
- `run_started`: beginning of active gameplay
- `run_checkpoint`: cumulative state at an active-play checkpoint
- `run_ended`: final available cumulative Run state

`session_started` is not an AWS-bound v2 event.

## Run Relationships

- Events in one Run share `run_id`, `game_version`, `schema_version`, and `source_type`.
- Exact retries retain the same `event_id`, payload, and `event_sequence`.
- Different payloads using the same `event_id` are conflicts.
- `event_sequence` determines gameplay order; network arrival order does not.
- Only the zero-time initial weapon choice may precede `run_started`.
- `upgrade_selected` must follow and match its `upgrade_options_shown` event.
- Checkpoint numbers, relative time, and cumulative counters do not decrease.
- Missing sequence values or a missing end produce an `INCOMPLETE` Run.
- Conflicts and impossible ordering produce an `INVALID` Run.
