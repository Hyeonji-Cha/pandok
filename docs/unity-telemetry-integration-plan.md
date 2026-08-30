# Unity P0 Telemetry Integration Plan

**Status**: Draft  
**Review baseline**: 2026-08-31  
**Scope**: P0 telemetry for one game Run

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
| Behavioral contract reference | `specs/001-run-telemetry-contract/contracts/telemetry-events-v1.md` |

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
| `event_id` | UUID used for retry and deduplication | Required |
| `event_name` | Event type | Required |
| `event_time` | UTC event occurrence time | Required |
| `anonymous_user_id` | Anonymous UUID with no direct identifier | Required; Unity creation and lifetime mapping pending |
| `session_id` | Application-session UUID | Required; Unity lifecycle mapping pending |
| `run_id` | UUID connecting one Run | Required for Run events |
| `game_version` | Game version that produced the event | Required |
| `schema_version` | Telemetry contract version | Required; current Draft value is `1.0` |

Retries must preserve both the original `event_id` and the original payload. Reusing an `event_id`
with different content is a conflict and will be rejected.

Schema `1.0` is recorded as `unused_draft`: it has not been consumed by a Unity build, external
service, or shared integration fixture. No additional developer confirmation is required for that
version decision.

## 5. Values Currently Identified as Available in Unity

The following values were identified during the earlier Unity code review. The developer must record
the exact class, property, or enum location used by the integration:

- player level;
- current XP;
- XP required for the next level;
- HP or HP percentage;
- cumulative Run kills;
- current gold balance;
- two-option level-up flows;
- three-option statue flows;
- confirmed `ChestItemType` values; and
- distinct death and player-restart end flows.

It is confirmed that `total_kills` starts at zero for each Run and is cumulative within that Run.

## 6. Values Requiring Additional Unity Work

The following values are optional in the current contract or outside the P0 executable scope. Do not
send them until Unity exposes a reliable counter or snapshot API:

- total XP acquired during the Run;
- total gold acquired during the Run;
- per-item acquisition counts;
- a complete active-upgrade snapshot;
- current effect values for each upgrade;
- miniboss reached and cleared counters;
- final stable string IDs for level-up weapons and upgrades; and
- local queue, retry, and purge behavior for network failures.

## 7. Confirmed Decisions and Remaining Questions

### Confirmed or Agreed

| Original question | Decision | Status |
|---:|---|---|
| 1 | The six P0 event emission points match the gameplay flow | Confirmed |
| 2 | Initial weapon selection occurs before `run_started` | Confirmed |
| 5 | `total_kills` resets to zero at Run start and is cumulative | Confirmed |
| 11 | Revoking consent must discard every unsent event | Policy agreed; Unity implementation evidence still required |
| 12 | Schema `1.0` is not externally consumed | Resolved as `unused_draft`; no developer review required |

### Remaining Developer Questions

The original numbers are retained for traceability. For each question, answer `Supported`,
`Change required`, or `Currently unavailable`, and provide the relevant code location.

| Number | Question | Answer | Unity code location or notes |
|---:|---|---|---|
| 3 | Which classes and properties provide `player_level`, XP, HP, kills, and gold? |  |  |
| 4 | Is `current_gold` the current balance, distinct from total gold acquired during the Run? |  |  |
| 6 | Do weapons and upgrades have stable string IDs suitable for persistence and analytics? |  |  |
| 7 | Can Unity create and retain `event_id`, `session_id`, and `run_id` UUIDs for their required lifetimes? |  |  |
| 8 | Can retries preserve the same `event_id` and byte-equivalent logical payload? |  |  |
| 9 | Can the Run-end path reliably distinguish `player_death` from `player_restart`? |  |  |
| 10 | Can Unity guarantee that no event is created or queued before explicit consent? |  |  |
| 13 | Are any contract fields unavailable or semantically different in the current Unity implementation? |  |  |

## 8. Unity Implementation Steps

### 8.1 Map Fields Before Emitting Events

1. Record the Unity class, property, or enum for every required field.
2. Confirm the value semantics and lifecycle, not only the data type.
3. Mark unavailable optional fields as omitted.
4. Report required-field mismatches before changing either the Schema or Unity behavior.

### 8.2 Implement Identifier Lifetimes

1. Create `anonymous_user_id` only within the approved consent lifecycle.
2. Create one `session_id` for the application session.
3. Allocate `run_id` before the initial weapon choice and retain it through `run_ended`.
4. Create a unique `event_id` once for each logical event.
5. Persist the original `event_id` and payload for retries.

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
85 passed
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
- zero purged events restored after application restart.

Record the Unity build version, test date, scenario steps, observed counts, code locations, and test
result for each scenario.

## 11. Required Developer Deliverables

Return the following items to the data team:

- answers to questions 3, 4, 6, 7, 8, 9, 10, and 13;
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

Verified locally on 2026-08-31:

- automated contract suite: `85 passed`;
- valid eight-record P0 Run sequence: accepted;
- valid CLI exit code: `0`;
- event containing `steam_id`: rejected with `prohibited_field`; and
- invalid CLI exit code: `1`.

The project targets Python 3.12. The current local compatibility verification was performed with
Python 3.11.2, so Python 3.12 verification remains pending.

## 13. Completion Criteria

The Unity integration is ready for acceptance when all of the following are true:

- all remaining developer questions are answered with code references;
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
- [Behavioral contract reference](../specs/001-run-telemetry-contract/contracts/telemetry-events-v1.md)
