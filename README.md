# PANDOK

PANDOK is a consent-based telemetry and multi-engine lakehouse project for **King Charles: Rise of the Alpha**.
It collects anonymous Run events, preserves immutable Bronze data, produces trusted Silver and Gold tables,
and generates developer-facing game improvement reports from verified Gold metrics.

## Current status

The P0 path has been implemented and verified with one consented production Run. PANDOK v2 is the only
AWS-bound event contract and follows the active [Privacy-by-Design baseline](docs/privacy-by-design.md).

Supported P0 events:

| Event | Purpose |
|---|---|
| `upgrade_options_shown` | Record choices actually displayed |
| `upgrade_selected` | Record and correlate the committed choice |
| `run_started` | Start active gameplay |
| `run_checkpoint` | Record cumulative state every 60 active seconds |
| `run_ended` | Record the final available Run summary |

## Privacy-by-Design target boundary

```text
Game Client
    -> Türkiye Anonymization Gateway
    -> privacy boundary
    -> AWS Sydney API Gateway
    -> Lambda Privacy Validator
    -> Kinesis -> Firehose -> S3 Bronze
    -> local Airflow -> Silver Iceberg -> Snowflake Gold Iceberg
    -> Athena reconciliation -> Bedrock report -> S3
```

The Game Client must not connect directly to AWS. The Türkiye gateway terminates the incoming request,
reconstructs an allow-listed payload, removes client-network headers, and creates a new outbound request.
Kinesis and Firehose can be disabled together when no game test is running. API Gateway, Lambda, and the
storage/catalog resources remain stable, so the developer-facing endpoint does not change between tests.

See [architecture](docs/architecture.md), [project scope](docs/project-scope.md), and the
[event contract](docs/event-contract.md) for the active project documentation.

## Privacy boundary

Telemetry must remain disabled until explicit consent. Revocation stops new events and deletes the unsent
local queue. Steam ID, nickname, email, device identifier, authentication token, chat content, precise
location, username, persistent player identifiers, client IP, original network headers, and free-form user
text must not cross from Türkiye into AWS Sydney.

Every Run receives a new random `run_id` that is never mapped to a player, device, installation, or another
Run. PANDOK does not claim that this design is exempt from KVKK; its privacy properties require technical and
operational verification.

Every event requires `source_type` so production, controlled-scenario, and load-test data remain separated.
All events in one Run must use the same value. Product analytics and Bedrock inputs include only
`CONSENTED_PROD_PLAY`.

## Local setup

```powershell
git clone https://github.com/Hyeonji-Cha/pandok.git
Set-Location .\pandok
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Validation

```powershell
pandok-contract validate-sequence tests/contract/fixtures/v2/valid/anonymous_p0_run_sequence.json
pandok-contract validate-event tests/contract/fixtures/v2/invalid/event_with_client_time.json
python -m pytest
```

Successful validation returns exit code `0`. Rejected input returns exit code `1` with a stable reason code,
message, field path, and event ID when available.

## Active documentation

| Purpose | Path |
|---|---|
| Project goal, scope, and completion criteria | `docs/project-scope.md` |
| Target architecture and service ownership | `docs/architecture.md` |
| Active Privacy-by-Design requirements and redesign phases | `docs/privacy-by-design.md` |
| Current telemetry field privacy decisions | `docs/privacy-field-review.md` |
| Identification threats, controls, tests, and residual risks | `docs/privacy-threat-model.md` |
| P0 event semantics and validation rules | `docs/event-contract.md` |
| Contract entities and invariants | `docs/event-data-model.md` |
| Local contract validation | `docs/contract-validation.md` |
| Unity implementation and evidence | `docs/unity-telemetry-integration-plan.md` |
| Verified end-to-end execution evidence | `docs/e2e-validation-2026-09-04.md` |
| Architecture decisions | `docs/decisions/` |

## Working method

PANDOK uses a lightweight contract-first workflow:

```text
scope and decision -> small implementation unit -> automated test -> execution evidence
```

## Last verified baseline

The repository records the following baseline from 2026-09-04:

- A full Python baseline passed 163 tests; the later report module passed its 11 focused tests.
- One `CONSENTED_PROD_PLAY` Run reached Bronze, Silver, Gold, and the AI report path.
- The Run contained 69 events and ended with `player_death` after 655.18 seconds.
- Snowflake and Athena returned the same Gold comparison result.
- Local Airflow completed the date-scoped Bronze-to-report DAG.
- Bedrock Nova Micro generated one English Markdown report with 3,259 total tokens.
- The report was stored under `ai-reports/report_date=2026-09-04/report.md`.

See the [E2E evidence](docs/e2e-validation-2026-09-04.md) for the observed counts, limitations, and shutdown
state. Re-run the full suite on Python 3.12 after changing the contract.
