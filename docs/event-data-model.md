# Data Model: Run Telemetry Contract

## Common Event

All P0 events contain these fields.

| Field | Meaning | Validation |
|---|---|---|
| `event_id` | Logical event identity, preserved across retries | UUID, required |
| `event_name` | P0 event category | One of six supported values, required |
| `event_time` | Time the gameplay fact occurred | UTC ISO 8601 date-time, required |
| `source_type` | Production play, controlled validation, or load testing | One of three supported values, required and consistent within a Run |
| `anonymous_user_id` | Random installation identity created after consent | UUID, required |
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
| `options` | Exactly the two displayed options | Array of exactly two unique slots |

Each option contains `slot`, stable `item_id`, `rarity`, and optional `level_before`.

### Upgrade Selected

References a prior choice with `choice_id` and `choice_sequence`. It records the selected slot, item,
rarity, Run time, optional player level, and optional before/after upgrade counts.

### Run Checkpoint

A cumulative Run state summary emitted every 60 seconds of active gameplay. It may contain level, XP
progress, health percentage, cumulative kills/XP/gold, pickup totals, miniboss progress, and a list of
active upgrades. Values that are present are type- and range-checked.

### Run Ended

The final available cumulative Run state. `end_reason` initially supports `player_death`,
`player_quit`, `run_completed`, `application_closed`, and `unknown`; unsupported game-specific reasons
require a compatible contract revision. A final upgrade list may be included.

## Nested Entities

### Upgrade Option

| Field | Validation |
|---|---|
| `slot` | Integer 1 or 2 |
| `item_id` | Stable lowercase identifier |
| `rarity` | Stable lowercase identifier |
| `level_before` | Non-negative integer when present |

### Upgrade State

| Field | Validation |
|---|---|
| `item_id` | Stable lowercase identifier |
| `upgrade_count` | Positive integer |

## Relationships and Invariants

- All Run events in a sequence share one anonymous user, session, Run, game version, and schema version.
- Event identifiers are unique within a logical sequence; exact repeated IDs represent delivery retries.
- `run_started` precedes other Run events by event time.
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
