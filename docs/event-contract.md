# Telemetry Events v1 Interface Contract

This document is the active behavioral reference for the executable schema in
`contracts/telemetry-event-v1.schema.json`. The current v1 draft predates the required
`source_type` field; production ingestion cannot be accepted until that field and its tests are added.

## Boundary

This contract describes one JSON object per telemetry event. The game client may retry delivery, but
it must preserve the original `event_id`. Event order is not guaranteed at the receiving boundary.

The executable source of truth will be `contracts/telemetry-event-v1.schema.json`. This document
explains behavioral rules that require more than single-document schema validation.

## Supported Events

| Event | Run ID | Purpose |
|---|---:|---|
| `session_started` | Optional | Begin one consented application session |
| `run_started` | Required | Begin active gameplay after initial weapon selection |
| `upgrade_options_shown` | Required | Record source-specific displayed upgrade options |
| `upgrade_selected` | Required | Record the player's linked selection |
| `run_checkpoint` | Required | Record cumulative Run state every 60 active seconds |
| `run_ended` | Required | Record the final available Run summary and end reason |

## Delivery Semantics

- Delivery is at least once: a valid event may be received more than once.
- An identical `event_id` and identical content is a retry duplicate.
- An identical `event_id` with different content is a conflict.
- Network arrival order is not a reliable gameplay order; use `event_time`, sequence fields, and
  identifiers when reconstructing a Run.
- A shown choice and its selection may share the same `event_time`; `choice_id` links them independently
  of arrival order. A selection with an earlier `event_time` than its shown choice is invalid.
- A missing `run_ended` or `session_ended` does not prove the player is still active.

## Upgrade Choice Rules

- Both `upgrade_options_shown` and `upgrade_selected` require the same `choice_source`.
- `level_up_weapon` and `level_up_upgrade` contain exactly two options using slots 1 and 2.
- `statue` contains exactly three distinct `ChestItemType` options using slots 1 through 3.
- The selected slot, item, and rarity must exactly match one option in the linked shown event.
- Supported rarity values are `common`, `uncommon`, `rare`, `epic`, and `legendary`.
- Confirmed `ChestItemType` identifiers are `horseshoe`, `gold_ingot`, `hourglass`, `sword`,
  `bull_skull`, `sticky_bone`, `greyhound_tooth`, and `blood_scent`.
- Chest rewards are automatic grants, not choices, and are reserved for the P1 `upgrade_granted`
  design rather than the P0 schema.

## Run Boundary

The game allocates `run_id` before initial weapon selection. Initial `level_up_weapon` shown and
selected events may precede `run_started` only with `run_elapsed_seconds` equal to zero. `run_started`
is emitted after that selection when active gameplay resumes. No other Run event may precede it.

## Upgrade State Semantics

`acquisition_count` describes how many times an item was granted; it is not an item level or current
effect. `effect_type` identifies an effect and its value may be a number or boolean. Acquisition
counters and complete effect snapshots are optional and marked `implementation required` until Unity
provides the required Run counters and Snapshot API.

Existing Unity code exposes player level, current XP, next-level XP, HP, cumulative kills, and current
gold. Total acquired XP, total acquired gold, per-item acquisition totals, complete active upgrades,
and miniboss reached/cleared counts require additional Unity instrumentation.

`run_ended.end_reason` includes `player_restart` in addition to the existing values.

## P1 Design Only

- `upgrade_granted` represents an automatic chest reward and does not imply player choice.
- Miniboss events include `wave_id`, `wave_number`, and `spawn_source`.
- `scheduled_wave` is produced by the regular 180-second `EnemySpawner` flow.
- `boss_summon` is produced every 30 seconds while Boss1 is alive by `BossMinibossSpawner`.
- `BossWaveSpawner` large boss waves begin at 15 minutes and repeat every five minutes; they are a
  separate boss-wave concept and must not be counted as miniboss waves.

## Consent Boundary

- No event may be created or sent before explicit consent.
- Revocation stops new events and discards unsent queued events.
- Direct-identifying fields are forbidden at all nesting levels.

## Compatibility

This contract is still an externally unused Draft, so the confirmed Unity corrections are applied
within schema version `1.0`. After external adoption, adding required fields or changing field meaning
or cardinality requires a new supported version or managed migration.

- Additive optional fields may be introduced without invalidating existing v1 fixtures only after
  documentation and tests are updated.
- Removing a field, changing its meaning or type, or making an optional field required is incompatible
  and requires a new supported schema version or an explicitly managed migration.
- Localized display names are presentation data and must never replace stable identifiers.

## Cross-Event Validation Results

The sequence validator returns a non-zero result when any event is invalid or when a relationship or
monotonicity rule fails. Each failure identifies the event when possible and supplies a stable reason
code plus human-readable detail.
