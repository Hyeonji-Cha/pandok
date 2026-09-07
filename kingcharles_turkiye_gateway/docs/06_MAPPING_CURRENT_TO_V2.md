# Current Unity / Phase 2.8 Gateway → PANDOK telemetry-event-v2 mapping

The canonical v2 JSON Schema is the source of truth. This mapping is a migration guide from the previously deployed Phase 2.8 payload shape; it does not relax v2 validation.

| Current / old field | v2 field | Rule |
|---|---|---|
| `event_id` | `event_id` | Preserve the UUID. Used for local HMAC dedupe and AWS idempotency. |
| `event_name` | `event_name` | Preserve for the five v2 events. `session_started` is removed and must not be sent. |
| `source_type` | `source_type` | Preserve `CONSENTED_PROD_PLAY` / `CONTROLLED_SCENARIO`; v2 also permits `LOAD_TEST`. |
| `anonymous_user_id` | — | REMOVE. It is not part of v2. |
| `session_id` | — | REMOVE. It is not part of v2. |
| `event_time` | — | REMOVE. Client wall-clock time is not part of v2. |
| `run_id` | `run_id` | Preserve a random UUID generated per Run. Never derive from player identity, IP, device data, or time. |
| — | `event_sequence` | NEW. Unity supplies a positive monotonically increasing sequence within the Run. |
| event-specific `run_elapsed_seconds` | common `run_elapsed_seconds` | Required on every v2 event; `run_started` must be 0. |
| `game_version` | `game_version` | Preserve, subject to v2 pattern/length. |
| `schema_version: "1.0"` | `schema_version: "2.0"` | Replace exactly. |
| `run_duration_seconds` on old `run_ended` | `run_elapsed_seconds` | Rename; v2 uses common elapsed seconds as Run duration. |

## Event-specific migration

### `run_started`
Old identity/time fields are removed. Add `event_sequence` and common `run_elapsed_seconds: 0`. Optional v2 fields `map_id`, `starting_max_hp`, and `starting_weapon_id` may be sent when Unity has them.

### `upgrade_options_shown`
Keep `choice_id`, `choice_sequence`, `choice_source`, and `options`; add common v2 fields. v2 permits `level_up_weapon`, `level_up_upgrade`, and `statue`. Non-statue choices contain exactly slots 1 and 2; statue contains exactly slots 1, 2, 3 and uses the contract chest item IDs. Optional acquisition/effect fields pass through when available.

### `upgrade_selected`
Keep the selected slot/item/rarity and choice identifiers. Add common v2 fields. Optional acquisition/effect before/after values pass through when available. Statue selection follows the contract chest item restrictions.

### `run_checkpoint`
Keep checkpoint/player-level/XP/HP/kills/gold metrics and common elapsed seconds. v2 additionally permits total XP/gold, hearts, healing, magnets, miniboss waves cleared, and bounded `active_upgrades`. Do not add fields not present in the canonical contract.

### `run_ended`
Remove old identity/time fields and `run_duration_seconds`; use common `run_elapsed_seconds`. Keep end reason/final level/kills/current gold. v2 additionally permits total XP/gold, hearts, healing, magnets, miniboss waves reached/cleared, and bounded `final_upgrades`.

## No mapping from request metadata
The Gateway does not create or modify `run_id` from request IP, request arrival time, headers, player/account data, or server timestamps. The validated v2 payload is exported unchanged to AWS.
