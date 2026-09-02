# Validate the PANDOK v2 Telemetry Contract

## Prerequisites

- Python 3.12
- Development dependencies installed
- No AWS account or game build is required

## Validate a Complete Run Sequence

From the repository root:

```powershell
uv run pandok-contract validate-sequence `
  .\tests\contract\fixtures\v2\valid\anonymous_p0_run_sequence.json
```

Expected outcome: exit code `0`, `valid: true`, and five accepted events.

## Verify Privacy Rejection

```powershell
uv run pandok-contract validate-event `
  .\tests\contract\fixtures\v2\invalid\event_with_client_time.json
```

Expected outcome: exit code `1` and a Schema rejection because exact client
`event_time` is not allowed in AWS-bound v2 events.

## Run Automated Tests

```powershell
uv run pytest -q
```

Expected outcome: every contract, privacy, sequence, ingestion, producer, and
integration test passes.
