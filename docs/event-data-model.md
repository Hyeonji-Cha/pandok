# Data Model: Run Telemetry Contract

## Common Event

All P0 events contain these fields.

| Field | Meaning | Validation |
|---|---|---|
| `event_id` | Logical event identity, preserved across retries | UUID, required |
| `event_name` | P0 event category | One of six supported values, required |
| `event_time` | Time the gameplay fact occurred | UTC ISO 8601 date-time, required |
| `source_type` | Production play, controlled validation, or load testing | One of three supported values, required and consistent within a Run |
| `anonymous_user_id` | Random pseudonymous identity created when telemetry is enabled | UUID, required; retained while consent remains, deleted on revocation, and regenerated after renewed consent |
| `session_id` | One application-session identity | UUID, required |
| `run_id` | One gameplay-attempt identity | UUID for Run events; optional for session start |
| `game_version` | Actual game build version | Non-empty stable string, required |
| `schema_version` | Telemetry contract version | `1.0`, required |

## Event Types

### Session Started

Marks a consented application session. It has common fields and does not require a Run identity.

### Run Started

Marks the beginning of active gameplay. Optional starting context includes map, maximum health, and
starting weapon when those concepts and values are available.

### Upgrade Options Shown

| Field | Meaning | Validation |
|---|---|---|
| `choice_id` | Identity shared with the later selection | UUID, required |
| `choice_sequence` | One-based choice order in the Run | Positive integer, required |
| `run_elapsed_seconds` | Active gameplay time | Non-negative number, required |
| `player_level` | Level when options appeared | Non-negative integer when present |
| `options` | Options actually displayed to the player | Two slots for level-up sources; three distinct items for `statue` |

Each option contains `slot`, stable `item_id`, and `rarity`. Optional state fields are
`acquisition_count_before`, `effect_type`, and `effect_value_before`.

### Upgrade Selected

References a prior choice with `choice_id` and `choice_sequence`. It records the selected slot, item,
rarity, Run time, optional player level, and optional before/after upgrade counts.

### Run Checkpoint

A cumulative Run state summary emitted every 60 seconds of active gameplay, excluding paused time.
Level, current XP, next-level XP, health percentage, literal cumulative kills, and current gold balance
are required. Additional cumulative totals and upgrade snapshots remain optional.

### Run Ended

The final available cumulative Run state. `end_reason` supports `player_death`, `player_quit`,
`player_restart`, `run_completed`, `application_closed`, and `unknown`. A final upgrade list may be
included.

## Nested Entities

### Upgrade Option

| Field | Validation |
|---|---|
| `slot` | Integer 1 or 2 for level-up sources; 1, 2, or 3 for `statue` |
| `item_id` | Stable lowercase identifier |
| `rarity` | Stable lowercase identifier |
| `acquisition_count_before` | Non-negative integer when present |
| `effect_type` | Stable lowercase identifier when present |
| `effect_value_before` | Number or boolean when present |

### Upgrade State

| Field | Validation |
|---|---|
| `item_id` | Stable lowercase identifier |
| `acquisition_count` | Positive integer |
| `effect_type` | Stable lowercase identifier when present |
| `effect_value` | Number or boolean when present |

## Relationships and Invariants

- All Run events in a sequence share one anonymous user, session, Run, game version, schema version, and source type.
- Event identifiers are unique within a logical sequence; exact repeated IDs represent delivery retries.
- Only the initial `level_up_weapon` shown and selected events may precede `run_started`, and both use
  `run_elapsed_seconds: 0` with the preallocated `run_id`.
- Each `upgrade_selected` references one `upgrade_options_shown` choice and matches one shown option.
- Choice sequence numbers and checkpoint numbers increase within a Run.
- Active Run time and cumulative counters do not decrease in event-time order.
- `run_ended` is terminal for the normal ordered sequence, while late delivery may arrive afterward.
- Two events with the same `event_id` but different content form a duplicate conflict and must be
  rejected or quarantined rather than silently selecting one.

## Privacy Constraints

Prohibited direct-identifier keys are rejected at any nesting depth. Contract v1 includes Steam ID,
Steam nickname, email, device identifier, authentication token, chat content, precise location,
username, and documented naming variants in this deny list.
