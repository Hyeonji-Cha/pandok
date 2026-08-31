# Validate the P0 Telemetry Contract

## Prerequisites

- Python 3.12
- A repository checkout with development dependencies installed
- No AWS account, credentials, game build, or Snowflake account is required

## Install

From the repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

On Linux or macOS, activate the environment with `source .venv/bin/activate`.

## Validate One Event

```powershell
pandok-contract validate-event tests/contract/fixtures/valid/run_started.json
```

Expected outcome: exit code `0` and a message identifying the event as valid.

## Validate a Complete Run Sequence

```powershell
pandok-contract validate-sequence tests/contract/fixtures/valid/p0_run_sequence.json
```

Expected outcome: exit code `0`; all events pass schema, privacy, relationship, and monotonicity checks.

## Verify Rejection

```powershell
pandok-contract validate-event tests/contract/fixtures/invalid/event_with_steam_id.json
```

Expected outcome: non-zero exit code and a privacy-specific rejection reason.

## Run Automated Tests

```powershell
python -m pytest
```

Expected outcome: all contract, privacy, fixture, and sequence tests pass. See
[event-data-model.md](event-data-model.md) for entity rules and [event-contract.md](event-contract.md)
for delivery semantics.
