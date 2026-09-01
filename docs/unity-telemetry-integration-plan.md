# Unity P0 Telemetry Integration Plan

- **Status**: Draft
- **Review baseline**: 2026-09-01
- **Scope**: P0 telemetry for Demo / Controlled Scenario integration

## 1. Purpose

This document tells the Unity developer what to review, implement, test, and return to the data team
before the P0 telemetry contract is accepted. The executable JSON Schema, Python validator, fixtures,
and automated contract tests already exist, but they are not yet connected to the Unity project.

The remaining work is to:

- map contract fields to concrete Unity classes, properties, and enums;
- implement any missing counters, snapshots, identifiers, and retry behavior;
- connect each event to the correct gameplay lifecycle point;
- prove that consent, local queue, retry, and purge behavior meets the privacy boundary; and
- export real Unity-generated JSON and validate it against this repository.

Do not populate unavailable fields with placeholder or fabricated values. Report the field as
unavailable and describe the required Unity implementation instead.

## 2. Repository Paths and Sources of Truth

Run all commands from the repository root.

| Purpose | Path |
|---|---|
| Executable event contract | `contracts/telemetry-event-v1.schema.json` |
| Cross-event and privacy validator | `src/pandok_contracts/validator.py` |
| CLI entry point | `src/pandok_contracts/cli.py` |
| Valid eight-event Run example | `tests/contract/fixtures/valid/p0_run_sequence.json` |
| Invalid examples | `tests/contract/fixtures/invalid/` |
| Contract tests | `tests/contract/` |
| Behavioral contract reference | `docs/event-contract.md` |

The executable JSON Schema is the source of truth for individual event shape and field constraints.
The Python validator is the source of truth for privacy, event relationships, ordering, retries, and
monotonic counters.

## 3. Confirmed P0 Event Lifecycle

| Event | Unity emission point | Purpose |
|---|---|---|
| `session_started` | After explicit consent, when the application session starts | Record the start of a consented anonymous session |
| `upgrade_options_shown` | When initial-weapon, level-up, or statue choices are actually displayed | Record the options shown to the player |
| `upgrade_selected` | When the player selection is committed | Record the selected option and link it to the shown choice |
| `run_started` | After the initial weapon is selected and active gameplay begins | Record the initial Run state |
| `run_checkpoint` | Every 60 seconds of active play, excluding paused time | Record cumulative Run state |
| `run_ended` | When death or player restart ends the Run | Record the final Run result |

The initial `level_up_weapon` choice is confirmed to occur before `run_started`. Both the shown and
selected events use a preallocated `run_id` and `run_elapsed_seconds: 0`:

```text
upgrade_options_shown -> upgrade_selected -> run_started
```

No other Run event may occur before `run_started`.

## 4. Required Common Fields

| Field | Meaning | Contract status |
|---|---|---|
| `event_id` | UUID used for retry and deduplication | Required; create once per logical event and never change during retry |
| `event_name` | Event type | Required |
| `event_time` | UTC event occurrence time | Required |
| `source_type` | Event source classification | Required; must match the approved producer and collection scenario |
| `anonymous_user_id` | Anonymous UUID with no direct identifier | Required; create when telemetry is enabled, delete on revocation, and regenerate after renewed consent |
| `session_id` | Application-session UUID | Required; create a new UUID for each consented application session |
| `run_id` | UUID connecting one Run | Required for Run events; allocate before initial weapon options are shown |
| `game_version` | Game version that produced the event | Required |
| `schema_version` | Telemetry contract version | Required; current Draft value is `1.0` |

Retries must preserve both the original `event_id` and the original payload. Reusing an `event_id`
with different content is a conflict and will be rejected.

Schema `1.0` is recorded as `unused_draft`: it has not been consumed by a Unity build, external
service, or shared integration fixture. No additional developer confirmation is required for that
version decision.

## 5. Values Currently Identified as Available in Unity

The developer policy identifies the following Unity mappings. Final acceptance still requires exact
code references and build-based evidence.

| Contract value | Unity source | Confirmed meaning |
|---|---|---|
| `player_level` | `PlayerXP.level` | Current player level |
| `current_xp` | `PlayerXP.currentXP` | XP within the current level |
| `xp_to_next_level` | `PlayerXP.xpToNextLevel` | Required XP threshold; greater than zero |
| `hp_percent` | Malbers Stats current/max health | Percentage from 0 through 100 |
| `total_kills` | Dedicated telemetry literal-death counter | Reset to zero per Run and increment once per confirmed enemy death |
| `current_gold` | `GoldCounterUI.GetGold()` | Current balance, not total acquired gold |
| stable `item_id` | `PandokTelemetryIds` | Stable analytics ID; never a localized display name |
| `rarity` | `UpgradeRarity` / `ChestRarity` | Base-weapon convention still requires final code evidence |

## 6. Values Requiring Additional Unity Work

The following values are optional in the current contract or outside the P0 executable scope. Do not
send them until Unity exposes a reliable counter or snapshot API:

- total XP acquired during the Run;
- total gold acquired during the Run;
- per-item acquisition counts;
- a complete active-upgrade snapshot;
- current effect values for each upgrade;
- miniboss reached and cleared counters;
- local queue, retry, and purge behavior for network failures.

## 7. Confirmed Decisions and Required Evidence

### Confirmed or Agreed

| Original question | Decision | Status |
|---:|---|---|
| 1 | The six P0 event emission points match the gameplay flow | Confirmed |
| 2 | Initial weapon selection occurs before `run_started` | Confirmed |
| 3 | Required gameplay values map to `PlayerXP`, Malbers Stats, a dedicated kill counter, and `GoldCounterUI` | Policy confirmed; exact code references still required |
| 4 | `current_gold` is current balance, not total gold acquired | Confirmed |
| 5 | `total_kills` resets to zero at Run start and is cumulative | Confirmed |
| 6 | Stable item IDs are provided through `PandokTelemetryIds` | Policy confirmed; code evidence still required |
| 7 | UUIDs use the lifetimes defined in section 8.2 | Policy confirmed; runtime evidence still required |
| 8 | Retries reuse the original `event_id` and payload without recalculation | Policy confirmed; runtime evidence still required |
| 9 | Death, restart, and quit produce distinct Run-end paths | Policy confirmed; runtime evidence still required |
| 10 | Consent defaults OFF and pre-consent event and queue counts remain zero | Policy confirmed; runtime evidence still required |
| 11 | Revoking consent must discard every unsent event | Policy agreed; Unity implementation evidence still required |
| 12 | Schema `1.0` is not externally consumed | Resolved as `unused_draft`; no developer review required |
| 13 | Unavailable optional values are omitted rather than replaced with placeholders | Confirmed |
| 14 | `anonymous_user_id` is created when telemetry is enabled, deleted on revocation, and regenerated after renewed consent | Confirmed |

### Remaining Implementation Evidence

The policy answers the earlier semantic questions, but it does not prove the shipped Unity behavior.
Return exact class and method locations, one unedited generated Run, and runtime evidence for UUID
lifecycle, consent-before-creation, queue purge, same-payload retry, and distinct Run-end paths.

## 8. Unity Implementation Steps

### 8.1 Map Fields Before Emitting Events

1. Record the Unity class, property, or enum for every required field.
2. Confirm the value semantics and lifecycle, not only the data type.
3. Mark unavailable optional fields as omitted.
4. Report required-field mismatches before changing either the Schema or Unity behavior.

### 8.2 Implement Identifier Lifetimes

1. Create `anonymous_user_id` when telemetry is explicitly enabled.
2. Retain it only while that consent remains active; delete it on revocation and create a new UUID
   after renewed consent.
3. Create one `session_id` for the application session.
4. Allocate `run_id` before the initial weapon choice and retain it through `run_ended`.
5. Create a unique `event_id` once for each logical event.
6. Persist the original `event_id` and payload for retries without rebuilding timestamps or snapshots.

### 8.3 Implement Choice Linking

1. Set `choice_source` to `level_up_weapon`, `level_up_upgrade`, or `statue`.
2. Use slots 1 and 2 for level-up choices.
3. Use slots 1, 2, and 3 for statue choices.
4. Ensure all statue options have distinct `item_id` values.
5. Reuse the shown event's `choice_id` in the selected event.
6. Ensure the selected source, slot, item, and rarity exactly match one shown option.
7. Never emit a selection with an earlier `event_time` than its shown event.

### 8.4 Implement Consent and Queue Behavior

1. Do not create telemetry before explicit consent.
2. Do not place telemetry in a local queue before explicit consent.
3. Stop creating and enqueueing new telemetry immediately after revocation.
4. Atomically discard every unsent queued event after revocation.
5. Verify that purged events do not reappear after an application restart.

The purge policy is agreed, but the contract remains Draft until Unity code references and build-based
test evidence prove this behavior.

### 8.5 Export a Representative Run

Export a JSON array generated by the actual Unity integration. It must include all six P0 event types
and follow the confirmed initial-weapon ordering. Do not hand-edit the exported payload before
validation.

## 9. Validation Procedure

### Install the Development Environment

Use the project environment described in `README.md`. The existing local virtual environment can be
used when available.

### Run the Full Contract Suite

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected result at the current baseline:

```text
92 passed
```

### Validate a Unity-Generated Run

```powershell
.\.venv\Scripts\pandok-contract.exe validate-sequence `
  path\to\unity-generated-run.json
```

Expected success response:

```json
{"valid": true, "event_count": 8, "issues": []}
```

### Validate One Unity-Generated Event

```powershell
.\.venv\Scripts\pandok-contract.exe validate-event `
  path\to\unity-generated-event.json
```

When validation fails, do not immediately edit the Schema. Return all of the following:

- the validator error code and field path;
- the Unity-generated JSON payload;
- the Unity class and method that produced the payload; and
- the reason Unity cannot currently satisfy the contract.

## 10. Consent and Privacy Evidence

The offline validator recursively rejects prohibited direct-identifier fields such as `steam_id`,
email addresses, device identifiers, authentication tokens, chat content, precise location, and user
names. Offline validation cannot prove runtime consent behavior.

Run Unity build scenarios that demonstrate:

- zero events created before consent;
- zero events queued before consent;
- no new events created or queued after revocation;
- zero unsent events remaining immediately after revocation; and
- zero purged events restored after application restart; and
- a new `anonymous_user_id` after telemetry is enabled again.

Record the Unity build version, test date, scenario steps, observed counts, code locations, and test
result for each scenario.

### 10.1 Network and Deployment Checks

- Never add an IP address to the telemetry payload.
- Review API Gateway, reverse-proxy, CDN, and access-log behavior separately from payload validation;
  minimize retention or mask network identifiers when they are not required.
- Permit HTTPS only for production telemetry endpoints.
- Keep real player-level raw JSON out of the public repository.
- Before global distribution, review the Privacy Notice, retention period, age policy, and any
  authorized access from Turkiye against the actual deployment and applicable legal requirements.
- Treat the developer policy as an engineering baseline, not as final legal advice.

## 11. Required Developer Deliverables

Return the following items to the data team:

- exact code references and runtime evidence for the confirmed policies in section 7;
- the list of changed Unity files;
- event-by-event Unity emission code locations;
- the class, property, and enum mapping for required fields;
- one unedited Unity-generated P0 Run JSON file;
- validator command output for that Run;
- the Unity build version and test date;
- consent and queue-purge scenario evidence;
- a list of unavailable fields; and
- the estimated implementation scope for unavailable required behavior.

## 12. Current Verification Baseline

Verified locally on 2026-09-01:

- automated contract suite: `92 passed`;
- valid eight-record P0 Run sequence: accepted;
- valid CLI exit code: `0`;
- event containing `steam_id`: rejected with `prohibited_field`; and
- invalid CLI exit code: `1`.

The project targets Python 3.12. The current local compatibility verification was performed with
Python 3.12.10.

## 13. Completion Criteria

The Unity integration is ready for acceptance when all of the following are true:

- all confirmed developer policies are backed by code references and runtime evidence;
- an unedited Unity-generated Run passes `validate-sequence`;
- all six P0 event types are emitted at the confirmed lifecycle points;
- shown and selected choices link correctly;
- retries preserve the original `event_id` and payload;
- required fields contain real gameplay values rather than placeholders;
- no telemetry is created or queued before consent;
- the unsent queue is empty after revocation and remains empty after restart; and
- unavailable optional fields are omitted and documented.

The contract remains Draft until the consent and queue-purge runtime evidence is accepted.

## 14. References

- [Repository usage and CLI commands](../README.md)
- [Executable JSON Schema](../contracts/telemetry-event-v1.schema.json)
- [Python validator](../src/pandok_contracts/validator.py)
- [Valid P0 Run example](../tests/contract/fixtures/valid/p0_run_sequence.json)
- [Invalid examples](../tests/contract/fixtures/invalid/)
- [Behavioral contract reference](event-contract.md)
