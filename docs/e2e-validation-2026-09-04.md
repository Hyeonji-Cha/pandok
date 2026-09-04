# PANDOK E2E Validation — 2026-09-04

이 문서는 실제 게임 Run이 수집부터 AI 보고서까지 도달했는지 확인한 실행 증적이다. 단일 Run의
연결성과 변환 정확도를 기록하기 위해 필요하며, 게임 전체 이용자의 행동을 대표하는 통계로 사용하지 않는다.

## Validation boundary

| Item | Observed value |
|---|---|
| Event contract | `telemetry-event-v2` |
| Source | `CONSENTED_PROD_PLAY` |
| AWS region | Sydney, `ap-southeast-2` |
| Pipeline date | `2026-09-04` |
| Orchestration | Local Airflow manual run |
| Final report | English Markdown in S3 |

## Verified path

```text
Unity -> Türkiye Gateway -> API Gateway -> Lambda -> Kinesis -> Firehose -> S3 Bronze
-> Silver reconstruction -> Silver Iceberg -> Snowflake Gold -> Athena reconciliation
-> Bedrock Nova Micro -> S3 AI report
```

Every Airflow task in the date-scoped run completed successfully. Snowflake and Athena returned the same
Gold comparison result before Bedrock was called.

## Observed game events

| Event | Count |
|---|---:|
| `run_started` | 1 |
| `run_checkpoint` | 10 |
| `upgrade_options_shown` | 29 |
| `upgrade_selected` | 28 |
| `run_ended` | 1 |
| **Total** | **69** |

The reconstructed Run ended with `player_death`. Its reported duration was **655.18 seconds**. The first
Silver execution was incomplete because Firehose had not delivered `run_ended` yet; re-running the same
date after delivery produced the complete result. This was delivery latency, not a schema or Unity error.

## Report evidence

| Item | Observed value |
|---|---|
| Model | `amazon.nova-micro-v1:0` |
| Input tokens | 2,668 |
| Output tokens | 591 |
| Total tokens | 3,259 |
| Stop reason | `end_turn` |
| S3 key | `ai-reports/report_date=2026-09-04/report.md` |

The estimated model charge for this single call was approximately **US$0.000176**, excluding the small
Athena query charge. The estimate is evidence for this invocation, not a guaranteed future price.

## Limits and shutdown state

- The sample contains one Run, so gameplay trends are not statistically meaningful yet.
- Firehose delivery is asynchronous; a recent Run may require waiting before a date backfill.
- Managed Flink and MWAA were not used.
- Kinesis and Firehose were disabled after the game test to avoid idle cost.
- API Gateway, Lambda, S3, Glue, and Athena configuration remain available for the next integration test.
