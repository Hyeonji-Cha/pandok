<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Added principles:
  - I. Consent and Data Minimization
  - II. Contract-First Telemetry
  - III. One Copy, Multiple Engines
  - IV. Verifiable and Recoverable Data
  - V. Cost-Aware, Reproducible Operations
- Added sections:
  - Architecture and Data Constraints
  - Specification-Driven Delivery
- Removed sections: none (template placeholders replaced)
- Deferred items: none
-->
# PANDOK Constitution

## Core Principles

### I. Consent and Data Minimization

Telemetry MUST be disabled until a player gives explicit consent. Revoking consent MUST stop new
collection and remove unsent queued events. The system MUST NOT collect direct identifiers such as
Steam ID, nickname, email, device identifier, authentication token, chat content, precise location,
or username. Only fields required for the documented gameplay analyses may be collected. Logs,
retention policies, and access controls MUST follow the same minimization rule as event payloads.

Rationale: production telemetry is useful only when player choice and privacy are protected across
the entire path, not merely in the game client.

### II. Contract-First Telemetry

Every event MUST conform to a versioned, machine-validatable contract before ingestion code or
analytics logic treats it as trusted data. Stable internal identifiers MUST be used instead of
localized display names. Contract changes MUST document compatibility, fixtures, and validation
tests. Facts awaiting confirmation from the game developer MUST remain marked as open questions
and MUST NOT silently become required fields or business rules.

Rationale: the game client and data platform are developed independently; a durable contract is
their shared boundary.

### III. One Copy, Multiple Engines

Amazon S3 MUST remain the authoritative storage layer for analytical data. Silver and Gold datasets
MUST use Apache Iceberg tables registered in a governed catalog so that Snowflake, Athena, and other
approved engines can operate on the same table data without maintaining independent analytical
copies. Any exception MUST document ownership, synchronization, cost, and deletion behavior.

Rationale: the project exists in part to demonstrate open-table interoperability and centralized
governance rather than engine-specific data duplication.

### IV. Verifiable and Recoverable Data

Processing MUST be idempotent by `event_id`. Invalid events MUST be quarantined with a reason and
MUST NOT contaminate trusted tables. Late-event rules, Bronze-to-Silver-to-Gold count reconciliation,
and date-scoped backfill MUST be testable. Every dashboard metric and AI-generated claim MUST be
traceable to a defined Gold metric; AI output MUST never be the source of record.

Rationale: a portfolio pipeline is credible only when its numbers can be explained, reproduced, and
repaired.

### V. Cost-Aware, Reproducible Operations

Core AWS resources MUST be declared in Terraform and environments MUST be separable by configuration.
Managed services are permitted when their role, behavior, and trade-offs are demonstrated through
contracts, transformations, tests, and observability. Bedrock MUST use an on-demand low-cost model,
receive aggregated Gold metrics only, and run at most once per analysis batch. Schedules, retention,
logging, and budgets MUST prevent idle or accidental spend.

Rationale: using managed infrastructure is an engineering choice, not a substitute for understanding
data semantics, failure modes, or cost controls.

## Architecture and Data Constraints

- The primary analytical unit is a game Run, not a stage.
- The intended flow is consented game telemetry through AWS ingestion into immutable S3 Bronze,
  validated and deduplicated Silver Iceberg tables, and analytics-ready Gold Iceberg marts.
- AWS Glue Data Catalog is the intended authoritative Iceberg catalog unless a feature specification
  records and justifies a different interoperable catalog.
- Snowflake performs analytical transformations against governed Iceberg data; Athena independently
  validates interoperability and selected results.
- High-frequency gameplay actions MUST be aggregated in the game client or checkpoints instead of
  producing one network request per frame, attack, hit, kill, XP orb, or damage event.
- Credentials, account identifiers, resource names, and deployment-specific endpoints MUST be
  configuration or secrets, never committed values.

## Specification-Driven Delivery

Work MUST follow the Spec Kit sequence: constitution, feature specification, clarification when
needed, implementation plan, tasks, consistency analysis, implementation, and convergence review.
Each specification MUST separate confirmed decisions from developer-pending questions. The first
implementation slice MUST be independently testable without a live game build; the telemetry event
contract and representative fixtures are the preferred starting boundary.

Each completed slice MUST include relevant automated tests, execution instructions, and evidence for
its acceptance criteria. Architecture changes MUST update the specification and plan before dependent
code is expanded. Scope MUST prioritize a complete P0 path over partially implemented optional
services.

## Governance

This constitution supersedes informal project notes when they conflict. Amendments require a written
rationale, an updated Sync Impact Report, and semantic versioning: MAJOR for incompatible principle
changes, MINOR for new or materially expanded governance, and PATCH for clarifications. Every feature
plan and review MUST include a constitution compliance check. Complexity or data duplication requires
explicit justification in the relevant plan. The repository owner approves governance amendments and
production telemetry activation.

**Version**: 1.0.0 | **Ratified**: 2026-08-29 | **Last Amended**: 2026-08-29
