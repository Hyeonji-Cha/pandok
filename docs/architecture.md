# PANDOK Architecture

## Target flow

```text
Steam consented players                    ECS Fargate Generator
CONSENTED_PROD_PLAY                   CONTROLLED_SCENARIO / LOAD_TEST
             \                                  /
              `-------> API Gateway <----------'
                           |
                     Ingestion Lambda
               schema validation + received_at
                           |
                  Kinesis Data Streams
                     /             \
                    /               \
             Data Firehose       Managed Flink
                    |          event time / watermark
                    |          dedup / late / Run state
                    |             /             \
             S3 Bronze JSON      /               \-> S3 Quarantine
             immutable source   v
                         S3 Silver Iceberg
                                  |
                         Glue Data Catalog
                                  |
                  Airflow -> Snowflake SQL
                  schedule / DQ / retry / backfill
                                  |
                           S3 Gold Iceberg
                       /          |           \
              Athena validation  |       Developer dashboard
                       \          |
                        metric comparison
                                  |
                         approved Gold metrics
                                  |
                       Report Lambda -> Bedrock
                                  |
                            S3 AI Reports
                                  |
                           Developer review
```

## Ownership

| Component | Single responsibility |
|---|---|
| API Gateway | Public HTTPS boundary and request limits |
| Lambda | Contract validation, server metadata, and Kinesis delivery |
| Kinesis | Durable fan-out buffer |
| Firehose | Independent Bronze delivery |
| S3 Bronze | Immutable replay and recovery source |
| Flink | Streaming correctness and Silver production |
| S3 Silver Iceberg | Trusted event and Run state |
| Quarantine | Invalid or excessively late records with reasons |
| Glue Data Catalog | Authoritative Silver and Gold Iceberg metadata |
| Snowflake | Silver analytics and Gold Iceberg transformation |
| Athena | Independent query and Gold metric reconciliation |
| Airflow | Ordering, retries, quality gates, and date backfills |
| Bedrock | Structured suggestions from approved aggregate metrics |

## Implementation sequence

1. Finalize the P0 contract.
2. Preserve Bronze JSON.
3. Implement the minimum Silver Plain Parquet path.
4. Reproduce duplicate, late-event, and date-backfill problems.
5. Record the Iceberg decision in an ADR.
6. Convert Silver to Glue-cataloged Iceberg.
7. Configure the Snowflake external volume and Glue REST catalog integration.
8. Create and populate Gold Iceberg with Snowflake SQL.
9. Query the same Gold table from Athena.
10. Automatically compare core metrics between both engines.
11. Let Airflow run transformation and validation in sequence.
12. Send only validated Gold metrics to Bedrock.

## Data trust gates

- Bronze stores accepted source records, including retries.
- Silver contains schema-valid, deduplicated records; invalid and too-late records go to Quarantine.
- Product Gold filters to `CONSENTED_PROD_PLAY`.
- Bedrock is blocked when Snowflake/Athena reconciliation or Gold quality checks fail.
- AI output is advisory and never the source of record.
