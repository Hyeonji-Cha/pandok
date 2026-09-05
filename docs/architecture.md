# PANDOK Architecture

This document describes the architecture implemented and verified on 2026-09-04. The Türkiye Gateway is
the privacy boundary; the Game Client does not connect directly to AWS.

## Target flow

```text
Password-protected Steam beta tester
CONSENTED_PROD_PLAY
          |
   Unity Game Client
          |
 Türkiye Gateway
 privacy removal + v2 reconstruction
          |
   AWS Sydney API Gateway
          |
   Ingestion Lambda
 JSON parsing + contract validation + received_at
          |
 Kinesis Data Streams -> Firehose -> S3 Bronze JSON
          |                optional streaming switch
          v
 Local Airflow (manual, date-scoped, no automatic retry)
          |
 Python Silver reconstruction
 dedup + event_sequence ordering + Run status
       /     \
      v       v
 Silver      Quarantine
 Parquet
      |
 Athena -> Glue Data Catalog -> Silver Iceberg
      |
 Snowflake reads Silver and creates Gold Iceberg in S3/Glue
      |
 Snowflake result <-> Athena result reconciliation
      |
 validated aggregate Gold metrics only
      |
 Bedrock Nova Micro -> S3 English Markdown report
      |
 Developer review
```

## Ownership

| Component | Single responsibility |
|---|---|
| API Gateway | Public HTTPS boundary and request limits |
| Lambda | Contract validation, server metadata, and Kinesis delivery |
| Kinesis | Short-lived streaming buffer, enabled only during ingestion tests |
| Firehose | Delivery from Kinesis to partitioned Bronze objects |
| S3 Bronze | Immutable replay and recovery source |
| Python Silver batch | Deduplication, sequence ordering, and Run reconstruction |
| S3 Silver Iceberg | Trusted event and Run state |
| Quarantine | Invalid or conflicting Runs with reasons |
| Glue Data Catalog | Authoritative Silver and Gold Iceberg metadata |
| Snowflake | Silver analytics and Gold Iceberg transformation |
| Athena | Independent query and Gold metric reconciliation |
| Local Airflow | Manual date-scoped ordering and quality gates; retries are disabled |
| Bedrock Nova Micro | One English report from approved aggregate metrics per DAG run |
| S3 AI report | Date-partitioned Markdown output; the same date is overwritten |

## Why Snowflake and Athena are both used

Game-version comparison does not technically require Snowflake; Athena can aggregate the same Iceberg data.
PANDOK uses Snowflake as the primary analytical workspace because the developer needs to repeatedly narrow
questions by game version, map, starting weapon, gameplay interval, and upgrade selection. This interactive
exploration role is separate from storage: Silver and Gold remain in S3 Iceberg rather than being locked into
Snowflake-only tables.

Athena is the independent validation engine. It reads the same Glue-cataloged Gold Iceberg tables and checks
defined core metrics after important transformations or releases, rather than duplicating every exploratory
Snowflake query. This separation gives Snowflake the analysis role and Athena the reproducibility role.

The same boundary supports a future natural-language analytics interface. Bedrock can translate a developer's
question into an allow-listed metric and filter specification, while a deterministic query layer executes the
aggregation against trusted Gold data. Bedrock explains the returned result; it does not calculate or invent
the metric itself.

## Implementation sequence

1. Finalize the P0 contract.
2. Preserve Bronze JSON.
3. Implement the minimum Silver Plain Parquet path.
4. Reproduce incomplete, retry, conflict, and date-backfill behavior.
5. Record the Iceberg decision in an ADR.
6. Convert Silver to Glue-cataloged Iceberg.
7. Configure the Snowflake external volume and Glue REST catalog integration.
8. Create and populate Gold Iceberg with Snowflake SQL.
9. Query the same Gold table from Athena.
10. Automatically compare core metrics between both engines.
11. Let Airflow run transformation and validation in sequence.
12. Send only validated Gold metrics to Bedrock.

All twelve steps were exercised successfully on 2026-09-04. This is an end-to-end implementation result,
not proof that the metrics are statistically representative; the real-game verification sample contains
one Run.

## Data trust gates

- Bronze stores accepted source records, including retries.
- Silver contains schema-valid, deduplicated records; invalid or conflicting Runs go to Quarantine.
- Product Gold filters to `CONSENTED_PROD_PLAY`.
- Bedrock is blocked when Snowflake/Athena reconciliation or Gold quality checks fail.
- AI output is advisory and never the source of record.

## Cost and shutdown boundary

- Managed Flink, NAT Gateway, and MWAA are not part of the implemented architecture.
- Local Airflow has `schedule=None`, zero task retries, and at most one active DAG run.
- Kinesis and Firehose are controlled by `enable_streaming` and are disabled outside game tests.
- S3 data has lifecycle limits, Athena uses the project workgroup, and Bedrock input/output sizes are capped.
- API Gateway and Lambda stay deployed so the public endpoint remains unchanged.
