# PANDOK

PANDOK is a consent-based game telemetry and lakehouse project for **King Charles: Rise of the
Alpha**. The project analyzes one gameplay Run rather than stage progression.

The target platform uses immutable telemetry on Amazon S3, Apache Iceberg tables shared across
multiple query engines, developer-facing analytics, and a low-cost AI insight summary. The first
implemented slice is deliberately smaller: an executable contract for the six P0 Run events that can
be validated before the game integration build is available.

## Current Slice: P0 Telemetry Contract

Supported events:

| Event | Required `run_id` | Purpose |
|---|---:|---|
| `session_started` | No | Start a consented application session |
| `run_started` | Yes | Start active gameplay after initial weapon selection |
| `upgrade_options_shown` | Yes | Record source-specific displayed upgrade choices |
| `upgrade_selected` | Yes | Record the linked player selection |
| `run_checkpoint` | Yes | Record cumulative state every 60 active seconds |
| `run_ended` | Yes | Record the final available Run summary |

Every event contains `event_id`, `event_name`, `event_time`, `anonymous_user_id`, `session_id`,
`game_version`, and `schema_version`. Run events also contain `run_id`. Retries preserve `event_id`.

Choice events require `choice_source`. `level_up_weapon` and `level_up_upgrade` use slots 1 and 2;
`statue` uses slots 1 through 3 and confirmed `ChestItemType` identifiers. The selected source, slot,
item, and rarity must match the linked shown event. Initial weapon choice events may use an allocated
`run_id` at zero elapsed time before `run_started`, which marks the resumption of active gameplay.

Unity currently exposes player level, current XP, next-level XP, HP, cumulative kills, and current
gold. Total acquired XP/gold, per-item `acquisition_count`, full active-upgrade state, effect values,
and miniboss progress remain optional and marked `implementation required` until the game supplies
Run counters or a Snapshot API. See the
[feature specification](specs/001-run-telemetry-contract/spec.md) for the exact boundary.

The contract remains an externally unused Draft, so the Unity-source corrections are applied within
schema version `1.0`. Automatic chest rewards (`upgrade_granted`) and miniboss/boss-wave telemetry are
P1 designs and are not accepted as P0 event names.

## Privacy Boundary

The game must produce no telemetry before explicit consent. Revocation stops new events and discards
the unsent local queue. The contract rejects prohibited identifier fields, including Steam ID,
nickname, email, device identifier, authentication token, chat content, precise location, and username.

## Local Setup on Windows

```powershell
cd C:\Users\ckgus\Desktop\workspace
git clone https://github.com/Hyeonji-Cha/pandok.git
cd pandok

py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If the repository is already cloned, use `git pull` instead of cloning it again.

## Validation Commands

Validate one event:

```powershell
pandok-contract validate-event tests/contract/fixtures/valid/run_started.json
```

Validate the representative Run sequence:

```powershell
pandok-contract validate-sequence tests/contract/fixtures/valid/p0_run_sequence.json
```

Verify that a privacy violation is rejected:

```powershell
pandok-contract validate-event tests/contract/fixtures/invalid/event_with_steam_id.json
```

Run the full test suite:

```powershell
python -m pytest
```

## Validation Result Format

Successful CLI validation returns exit code `0` and JSON similar to:

```json
{"valid": true, "event_count": 8, "issues": []}
```

Rejected input returns exit code `1`, `valid: false`, and one or more issues with a stable `code`,
human-readable `message`, field `path`, and `event_id` when available.

Stable reason codes:

- `invalid_json`
- `schema_invalid`
- `prohibited_field`
- `duplicate_conflict`
- `correlation_mismatch`
- `missing_run_start`
- `event_order_invalid`
- `choice_not_found`
- `choice_mismatch`
- `counter_decreased`

## Spec Kit Workflow

Project decisions and implementation are governed by Spec Kit artifacts:

- Constitution: `.specify/memory/constitution.md`
- Feature specification: `specs/001-run-telemetry-contract/spec.md`
- Technical plan: `specs/001-run-telemetry-contract/plan.md`
- Executable tasks: `specs/001-run-telemetry-contract/tasks.md`

The next infrastructure features will be specified separately after this contract slice is stable.

## Verified Results

Verified on 2026-08-30 in the available Python 3.11 compatibility environment; the project target
remains Python 3.12:

- JSON Schema Draft 2020-12 self-validation: passed
- Automated contract suite: 85 passed
- Valid single-event CLI example: passed
- Valid eight-record P0 Run sequence covering all six event types: passed
- Two-option level-up and three-option statue conditional validation: passed
- Three distinct statue item identifiers and duplicate-item rejection: passed
- Pre-Run initial weapon choice and linked source validation: passed
- Same-time shown/selected links are independent of network arrival order: passed
- Prohibited `steam_id` fixture: rejected with `prohibited_field`
- 10,000 single-event validations: completed below the 10-second acceptance threshold
- Python bytecode compilation and Git whitespace checks: passed
