# ADR 0001: Silver 저장 형식으로 Apache Iceberg 사용

- 상태: Accepted
- 결정일: 2026-09-03

## 배경

PANDOK은 Bronze JSON을 중복 제거하고 Run 단위로 복원한 뒤 Silver에 저장한다.

Plain Parquet 기준선으로 다음 항목을 확인했다.

- 날짜 파티션 저장
- Athena 조회
- retry 중복 제거
- INVALID Run Quarantine 분리
- 날짜 backfill
- 교차 날짜 Run 복원

이후 Snowflake와 Athena가 같은 Silver 데이터를 조회하고, 재처리 결과를 안전하게 갱신할 수 있어야 한다.

## 결정

신뢰 가능한 Silver의 공식 저장 형식으로 Glue Catalog 기반 Apache Iceberg v2를 사용한다.

구조는 다음과 같다.

```text
S3 Bronze JSON
→ Python Run reconstruction
→ Silver Plain Parquet staging
→ Athena Iceberg write
→ Glue silver_events_iceberg
→ Snowflake Glue REST Catalog