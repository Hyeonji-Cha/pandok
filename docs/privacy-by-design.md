# Privacy-by-Design Telemetry Baseline

This document records the active privacy requirements for PANDOK and explains why implementation is paused
before further Unity or AWS ingestion work. It is a technical design baseline, not a legal conclusion.

## Status

- Privacy redesign is active.
- Direct Game Client-to-AWS telemetry is prohibited.
- Existing contract, ingestion, and Terraform code must be assessed before being extended.
- No document may claim that this architecture is exempt from KVKK or that legal review is unnecessary.
- Existing repository structure takes precedence; removed `spec.md`, `plan.md`, and `tasks.md` files must not
  be recreated. Design decisions belong in the active `docs/` set and short ADRs.

## Design objective

AWS Sydney and the Korean data engineer must receive only gameplay telemetry that cannot be used to identify
a person, Steam account, device, network identity, or link separate Runs to the same player.

> Do not protect personal data after it reaches AWS. Prevent player-identifiable data from reaching AWS in
> the first place.

The privacy properties depend on the implemented schema, Türkiye infrastructure and provider behavior,
logging configuration, operational controls, and future changes. They must be reviewed again whenever those
elements change.

## Required flow and trust boundary

```text
King Charles Game Client
        |
        | HTTPS
        v
Türkiye Anonymization Gateway
  Nginx TLS termination
        |
  FastAPI Privacy Gateway
  - schema validation
  - allowed-field reconstruction
  - forbidden-field detection
  - header sanitization
  - new outbound request

======== PRIVACY BOUNDARY: IDENTIFIABLE DATA MUST NOT CROSS ========
        |
        v
AWS Sydney (ap-southeast-2)
  API Gateway
        -> Lambda Privacy Validator
        -> Kinesis Data Streams
        -> Managed Apache Flink
        -> Data Firehose
        -> S3 Bronze
        -> S3 Silver
        -> Airflow batch processing
        -> Gold aggregate metrics
        -> LLM report
```

The Game Client must never connect directly to AWS API Gateway or Kinesis. If the Türkiye gateway is
unavailable, telemetry transmission is disabled and gameplay continues normally.

## Data that must not reach AWS

The following data is prohibited in payloads, headers, logs, errors, failed-record storage, queues, backups,
CloudWatch, Kinesis, Firehose, S3, Airflow, Gold data, and LLM input:

- player IP and client-network metadata;
- Steam ID, Steam account ID, nickname, and authentication data;
- player, user, account, device, machine, installation, or hardware identifiers;
- MAC address, persistent identifier, and fingerprint;
- email, name, phone number, Discord ID, and precise location;
- operating-system username and file paths containing a username;
- authentication tokens, session tokens, cookies, and authorization headers;
- original HTTP headers, including `X-Forwarded-For`, `Forwarded`, `X-Real-IP`, `CF-Connecting-IP`, and
  `True-Client-IP`;
- free-form fields capable of carrying identifiers.

Hashing a Steam ID or renaming a persistent identifier does not make it acceptable.

## Game Client requirements

The client creates only analytics-required gameplay fields. It applies a local privacy filter and local
schema validation before transmission. It must not use a collect-everything-then-anonymize-later model.

Consent remains required. When telemetry is turned off, the client stops creating and transmitting events
and deletes its pending local queue. A local retry buffer may contain only permitted anonymous telemetry,
must have a retention upper bound, and must be deleted after successful transmission.

## Run identity and time

- Generate a new random `run_id` at the start of every Run.
- Never reuse it in another Run.
- Never map it to a Steam, player, device, machine, installation, or account identifier.
- Do not create a mapping table, persistent local identifier, or server-side player fingerprint.
- AWS must not be able to determine that two Runs came from the same player.
- Preserve Run-internal ordering with relative values such as `elapsed_sec`, `elapsed_ms`, and
  `event_sequence`.
- Avoid precise wall-clock timestamps in gameplay payloads. If operational grouping is essential, use a
  coarse identifier such as `test_batch_id` and reassess its identification risk.

## Türkiye gateway requirements

The gateway is not a reverse proxy. It terminates the incoming connection, validates the body, constructs a
new object from an explicit allow-list, removes incoming headers, and creates a new outbound request to AWS.
Unknown fields and forbidden-field variants in snake_case, camelCase, or different letter case are rejected.

The initial forbidden-key guard includes `steam_id`, `steamid`, `steam_account_id`, `player_id`, `user_id`,
`account_id`, `device_id`, `machine_id`, `installation_id`, `hardware_id`, `mac`, `ip`, `ip_address`, `email`,
`username`, `nickname`, `auth`, `auth_token`, `token`, `cookie`, `session`, `location`, `latitude`, `longitude`,
and `x_forwarded_for`. The list must be expanded after the repository-wide field review.

Nginx access logging is disabled by default. Request bodies, client IP, User-Agent, Referer, Cookie,
Authorization, identifying query strings, and raw headers must not be logged. Error logging must also be
tested for accidental payload or identifier capture. The deployment must be physically located in Türkiye,
must not add an overseas CDN, external APM, third-party analytics, or unnecessary backups by default, and
must not forward client-network metadata abroad. A provider is not selected during the initial redesign.

## Gateway-to-AWS security

Only the Türkiye gateway may submit telemetry to the AWS ingestion endpoint. An API key alone is not the
sole security control. Credentials must not be embedded in the Game Client, source repository, telemetry,
or logs. The authentication mechanism and secret storage method are selected after the current repository
and infrastructure are assessed.

## AWS ingestion requirements

API Gateway applies authentication, request-size limits, rate limits, throttling, and privacy-minimized
access logging. Lambda performs a second independent validation of schema version, allowed fields,
forbidden fields, types, and payload size. Rejected requests must never reach Kinesis.

Lambda must not log raw events or request bodies. Operational logs are limited to non-identifying values
such as schema version, event type, validation result, stable error code, and processing duration. Logging a
`run_id` requires a documented operational need.

Kinesis may use the per-Run random `run_id` as its partition key to preserve ordering within one Run. No AWS
component may create or infer a persistent player fingerprint or join separate Runs as one player.

## Medallion and analytics requirements

In PANDOK, Bronze means validated anonymous gameplay events that passed both the Türkiye and AWS privacy
gates. It never means the original player network request.

```text
Bronze != raw personal request
```

Silver contains cleaned, normalized, or Run-level data. Gold contains aggregate game-improvement metrics.
The LLM receives validated Gold aggregates by default, not raw gameplay events.

Required analysis includes Run duration, death timing and cause, level reached, kill/XP/HP/gold progression,
upgrade choices and combinations, pickups, enemy and miniboss encounters, survival time, problematic
gameplay intervals, balance anomalies, Gold metrics, and evidence-backed LLM suggestions.

Intentionally excluded analysis includes cross-Run player tracking, individual retention, player history,
identity cohorts, user-level behavior, and searches for a particular user's historical data.

## Retention and cost controls

AWS telemetry has a default upper bound of 30 days. S3 objects, CloudWatch logs, failed records, gateway
logs, local buffers, and Airflow logs require explicit retention. Anything retained longer requires a
documented reason. Infrastructure design continues to use low-cost development defaults, bounded inputs,
least-privilege IAM, and explicit review before chargeable AWS resources are applied.

## Mandatory field review

Before changing the executable schema, every current telemetry field must be classified:

| Field | Current location | Analysis purpose | Identification risk | Decision | Reason |
|---|---|---|---|---|---|
| To be assessed | To be assessed | To be assessed | To be assessed | `KEEP`, `MODIFY`, or `REMOVE` | To be assessed |

Names alone are not sufficient evidence that a field is anonymous. Direct identifiers, indirect
identifiers, rare value combinations, timestamps, and external matching risk must all be considered.

## Mandatory automated privacy evidence

Tests must demonstrate that:

- valid anonymous telemetry passes;
- Steam, player, user, IP, device, machine, persistent identifiers, and unknown fields fail;
- incoming forwarding and client-IP headers never reach the AWS request;
- the gateway creates a new outbound request rather than forwarding the original request;
- schema-invalid or privacy-invalid requests never reach Kinesis;
- no Steam-to-Run, device-to-Run, or cross-Run player mapping exists;
- gateway and AWS logs contain neither client IP nor raw request bodies;
- AWS logs do not contain player IP or persistent player identifiers.

## Redesign phases

1. Perform a read-only repository analysis.
2. Document the current telemetry data flow.
3. Classify every telemetry field as `KEEP`, `MODIFY`, or `REMOVE`.
4. Analyze privacy threats and identifiability risks.
5. Design the anonymous telemetry schema.
6. Design the new architecture and present Phases 1-6 for review.
7. Update the active scope, architecture, contract, data-model, and decision documents after approval.
8. Modify Game-side telemetry.
9. Implement the Türkiye gateway.
10. Implement AWS API Gateway and Lambda privacy validation.
11. Adapt the Kinesis, Flink, Firehose, medallion, batch, Gold, and LLM paths.
12. Resume Terraform implementation only after the privacy design is approved.
13. Add automated privacy tests and update final operational documentation.

## Success criteria

Using only data accessible in AWS Sydney, no operator or service must be able to identify a Steam account,
person, device, player IP, or determine that separate Runs came from the same player. The Game Client must
have no direct AWS path, and the Türkiye gateway must terminate the incoming request, reconstruct an
allow-listed payload, sanitize headers, and create a new outbound request.

