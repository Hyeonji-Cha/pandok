# PANDOK Project Scope

## Goal

Collect anonymous telemetry from consenting Steam players, transform incomplete and retry-prone events into
trusted Run analytics, and provide traceable improvement evidence to the game developer.

## P0 scope

- Explicit opt-in, revocation, and unsent-queue deletion
- Versioned JSON event contract and automated validation
- API Gateway, Lambda, Kinesis, Firehose, and immutable S3 Bronze JSON
- Flink Event Time, Watermark, deduplication, late-event handling, and Quarantine
- Plain Parquet baseline followed by an evidence-backed Silver Iceberg transition
- AWS Glue Data Catalog as the shared Iceberg catalog
- Snowflake transformations that create Gold Iceberg tables in S3
- Athena queries against the same Gold tables and automatic metric comparison
- Airflow scheduling, quality checks, retries, and date-scoped backfills
- Bedrock report generation from validated Gold metrics only
- At least one real consented event traced end to end

## Data sources

| `source_type` | Purpose | Product analytics |
|---|---|---|
| `CONSENTED_PROD_PLAY` | Natural play by consenting Steam users | Included |
| `CONTROLLED_SCENARIO` | Reproducible functional and edge-case tests | Excluded |
| `LOAD_TEST` | Throughput, backpressure, and recovery tests | Excluded |

`source_type` is required by the executable v2 contract. Events in one Run must use the same value, and
the same `event_id` cannot be reused with a different source. Collection channels must later verify that the
producer is authorized to use the supplied value.

## Out of scope

- Steam ID, nickname, email, device identifiers, chat content, or free-form player text
- Databricks, Kubernetes, a separate Spark platform, RAG, or a custom ML model
- Treating synthetic traffic as real users
- Generalizing a small tester sample to the whole player population
- Unapproved high-cost AWS resources such as NAT Gateway or MWAA
- Autonomous game changes based on AI output

## Completion criteria

- A consenting player's event reaches Gold.
- Duplicate events do not duplicate trusted metrics.
- Invalid and excessively late events are separated with reasons.
- Late-event and timeout rules are reproducible in tests.
- A selected date can be backfilled.
- Bronze, Silver, Quarantine, and Gold count differences are explainable.
- Snowflake and Athena agree on defined Gold metrics.
- Bedrock numbers are traceable to validated Gold metric IDs.
- Terraform reproduces the core AWS infrastructure.
- README and evidence documents are sufficient to understand and demonstrate the system.

## Delivery method

Every work unit records its purpose, changed files, validation command, observed result, remaining risk, and
next step. Major architecture choices are recorded as short ADRs under `docs/decisions/`.
