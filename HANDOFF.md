# HANDOFF

이 문서는 다른 데스크톱의 Codex가 PANDOK 작업을 중복 조사 없이 이어가기 위한 최신 인수인계 문서다.
새 작업을 시작하기 전에 이 문서와 실제 `git status`, 최근 커밋을 함께 확인한다.

## 프로젝트 목표

Steam 게임 **King Charles: Rise of the Alpha**의 익명 gameplay telemetry를 수집하고,
신뢰할 수 있는 Bronze, Silver, Gold 데이터로 변환하는 개인 데이터 엔지니어링 프로젝트다.

사업용 서비스 구축이 아니라 데이터 수집·검증·스트리밍·분석 구조를 직접 학습하고 증명하는 것이 목적이다.

## 공식 아키텍처

```text
Unity
→ Türkiye Gateway
→ 개인정보 제거·v2 Schema 검증·중복 처리
→ AWS API Gateway HTTP API
→ Lambda: 인증·JSON parsing·v2 재검증·Bronze wrapper
→ Kinesis Data Streams
→ Data Firehose
→ S3 Bronze
→ Silver Run 복원
→ Gold 집계·분석
```

- AWS Region은 Sydney `ap-southeast-2`다.
- Managed Apache Flink는 현재 구성에 포함하지 않는다. 필요한 상태 기반 실시간 처리가 명확해질 때만 검토한다.
- 데이터베이스는 초기 범위에 포함하지 않는다. S3, Glue, Athena 기반 데이터 레이크로 진행한다.
- 로컬 Bronze writer와 Lambda 직접 S3 writer는 구현하지 않는다.

## 확정된 v2 데이터 계약

- AWS 입력 계약은 `contracts/telemetry-event-v2.schema.json` 하나만 사용한다.
- v1 계약과 v1 validator 흔적은 제거했으며 다시 추가하지 않는다.
- 유지 필드: `run_id`, `event_id`, `event_sequence`, `run_elapsed_seconds`.
- `run_id`는 Run마다 새로 만들며 서로 다른 Run이나 player와 연결하지 않는다.
- `event_id`는 논리 이벤트마다 새로 만들고 동일 이벤트 재전송에서는 유지한다.
- 사용자·계정·Session·IP·기기·설치 식별자와 정확한 client `event_time`은 AWS로 보내지 않는다.
- `session_started`는 AWS로 보내지 않는다.
- `event_sequence`로 Run 내부 순서를 복원하고 `run_elapsed_seconds`로 상대시간을 표현한다.
- `source_type`은 `CONSENTED_PROD_PLAY`, `CONTROLLED_SCENARIO`, `LOAD_TEST`를 구분한다.
- 운영 데이터는 `turkiye_gateway` ingestion channel만 허용한다.
- `aggregate-export-v1`은 Türkiye Gateway의 선택적 대조 자료일 뿐 v2 이벤트를 대체하지 않는다.

## Türkiye Gateway 상태와 책임

- Türkiye VPS와 Gateway는 게임 개발자이자 운영자가 소유·관리한다.
- 개발자가 VPS에서 게임 데이터가 들어오는 것까지 확인했다.
- Unity가 AWS에 직접 연결하거나 Gateway 장애 시 AWS로 fallback하는 경로는 금지한다.
- Gateway는 원본 header를 전달하지 않고 허용된 v2 payload로 새 AWS 요청을 만들어야 한다.
- `X-Forwarded-For`, `Forwarded`, `X-Real-IP` 등 player IP header를 AWS로 전달하지 않는다.
- access log, request body log, 외부 APM, 불필요한 backup은 끄거나 최소화한다.
- AWS 배포 후 개발자에게 API endpoint와 공유 비밀값을 안전하게 전달해야 한다.
- Gateway는 AWS 요청에 `X-Pandok-Ingestion-Key` header를 포함해야 한다.

## 구현 완료

### Python ingestion

- `src/pandok_ingestion/pipeline.py`
  - `validate_anonymous_event()`로 v2 계약과 개인정보 금지 규칙 검사.
- `src/pandok_ingestion/bronze.py`
  - 검증된 이벤트를 Bronze envelope로 포장.
  - 운영 source와 ingestion channel 조합 검사.
- `src/pandok_ingestion/handler.py`
  - JSON 문자열을 Python 객체로 파싱.
  - 파싱 → 검증 → Bronze → Kinesis 흐름 연결.
- `src/pandok_ingestion/kinesis_producer.py`
  - Bronze JSON을 UTF-8 newline-delimited record로 직렬화.
  - `run_id`를 Kinesis Partition Key로 사용.
- `src/pandok_ingestion/lambda_entrypoint.py`
  - API Gateway HTTP API payload 2.0 처리.
  - 공유 비밀값을 `hmac.compare_digest()`로 검사.
  - request body를 64 KiB로 제한.
  - 정상 요청은 `202`, 인증 실패는 `401`, 잘못된 telemetry는 `400` 반환.
  - 요청 본문이나 비밀값을 로그·응답에 기록하지 않음.

### Terraform infrastructure

- `infra/storage_s3.tf`
  - 비공개 S3 Bronze bucket, SSE-S3, HTTPS-only policy.
  - Bronze 객체 30일 후 삭제, incomplete multipart upload 7일 후 삭제.
- `infra/streaming_kinesis.tf`
  - Provisioned Kinesis, 기본 shard 1개, 보존 24시간, AWS 관리형 KMS 키.
- `infra/streaming_firehose.tf`
  - Kinesis source → S3 Bronze.
  - 5 MiB 또는 300초 buffer, GZIP 압축.
  - `bronze/received_date=YYYY-MM-DD/` 저장.
  - Firehose 전용 최소 IAM 권한을 같은 파일에서 관리.
- `infra/ingestion_lambda.tf`
  - Python 3.12 Lambda와 전용 IAM.
  - 메모리 256 MB, timeout 10초, 예약 동시 실행 기본 5.
  - CloudWatch log retention 7일.
- `infra/ingestion_api.tf`
  - 저비용 HTTP API와 `POST /telemetry/v2` 단일 route.
  - payload format 2.0, access log와 detailed metric 비활성.
  - 기본 rate 20 requests/sec, burst 40.
  - API Gateway의 route는 `authorization_type = NONE`이지만 Lambda에서 공유 비밀값을 검사한다.
- `scripts/build_lambda_package.ps1`
  - Windows에서 Python 3.12 Linux x86_64 Lambda ZIP 생성.
  - 출력은 `build/pandok-ingestion-lambda.zip`이며 Git에서 제외된다.

## 비용 제어 기준

- `enable_streaming` 기본값은 `false`다.
- `false`에서는 Kinesis, Firehose, Lambda, API Gateway와 관련 IAM·로그 그룹을 만들지 않는다.
- `true`는 짧은 AWS 통합 시험 동안만 사용한다.
- Kinesis shard는 기본 1, validation 상한 2다.
- Lambda 메모리는 128/256/512 MB만 허용하며 기본 256 MB다.
- Lambda timeout은 3~15초만 허용하며 기본 10초다.
- Lambda 예약 동시 실행은 기본 5, 상한 10이다. 예약 설정 자체에는 유휴 실행 비용이 없다.
- API Gateway throttle은 비용의 절대 상한이 아니라 best-effort 보호 장치다.
- NAT Gateway, MWAA, OpenSearch, RDS와 고객 관리 KMS 키는 현재 사용하지 않는다.
- 작업 종료 후 `enable_streaming=false`로 적용해 시간당 비용이 있는 스트리밍 리소스를 제거한다.

## 비밀값과 로컬 파일

- `infra/terraform.tfvars`에 32바이트 Base64 공유 비밀값이 설정되어 있다.
- 현재 데스크톱에서는 형식과 Git 제외를 확인했다.
- `terraform.tfvars`와 Terraform state는 Git에 올리지 않는다.
- 다른 데스크톱으로 Git만 이동하면 이 파일은 따라가지 않는다.
- 새 데스크톱에서는 새 비밀값을 생성하거나 기존 값을 별도의 안전한 방법으로 전달해야 한다.
- 비밀값을 채팅, 문서, 커밋, 명령 출력에 노출하지 않는다.
- 개발자에게는 API endpoint와 비밀값을 서로 분리된 안전한 채널로 전달한다.

## 현재 검증 상태

2026-09-02 기준:

```text
uv run pytest -q
75 passed in 4.71s

terraform fmt -check
통과

terraform validate
Success! The configuration is valid.

terraform plan -var="enable_streaming=true"
Plan: 19 to add, 0 to change, 0 to destroy
```

Terraform plan에서 공유 비밀값은 `(sensitive value)`로 가려지는 것을 확인했다.
아직 `terraform apply`는 실행하지 않았고 AWS 리소스 및 비용은 생성되지 않았다.

## 다음 작업

### 1. 새 데스크톱 준비

```powershell
git pull
uv sync
& .\scripts\build_lambda_package.ps1
```

- `infra/terraform.tfvars`의 공유 비밀값을 새로 설정하거나 안전하게 이전한다.
- 정상 빌드 결과는 `build\pandok-ingestion-lambda.zip`이다.

### 2. 배포 직전 계획 재확인

```powershell
terraform -chdir=infra init
terraform -chdir=infra plan -var="enable_streaming=true"
```

정상 예상 결과는 `19 to add, 0 to change, 0 to destroy`다.

### 3. 짧은 AWS 통합 시험

사용자 확인 후에만 다음 apply를 실행한다.

```powershell
terraform -chdir=infra apply -var="enable_streaming=true"
```

검증 순서:

1. Terraform output의 `ingestion_api_endpoint` 확인.
2. 잘못된 공유 비밀값 요청이 `401`인지 확인.
3. `CONTROLLED_SCENARIO` 이벤트 1건을 올바른 비밀값으로 보내 `202` 확인.
4. 최대 5분 이상 기다린 뒤 S3 `bronze/received_date=.../`의 GZIP 객체 확인.
5. GZIP JSON을 읽어 v2 event, Bronze metadata, `turkiye_gateway` channel 확인.

### 4. 시험 종료 후 비용 중단

```powershell
terraform -chdir=infra apply -var="enable_streaming=false"
```

- 실행 전 plan에서 Kinesis, Firehose, Lambda, API Gateway 관련 리소스가 제거되고 S3는 유지되는지 확인한다.
- 중요한 데이터가 생긴 뒤에는 S3 삭제 여부를 별도로 검토한다.

### 5. 데이터 레이크 다음 단계

- 실제 AWS 수집 경로 확인 후 Silver Run 복원 구현.
- `event_sequence` 중복·공백·충돌을 반영해 `VALID`, `INCOMPLETE`, `INVALID` 상태 생성.
- Glue Catalog와 Athena table은 실제 S3 객체 구조를 확인한 뒤 추가.
- Gold 집계는 Silver 계약이 안정된 후 구현.

## 커밋에서 제외할 사용자 파일

- `infra/terraform.tfvars`
- `build/` 전체
- Terraform state와 `.terraform/`
- 현재 untracked 상태인 `docs/6조_판독_데이터파이프라인_기획서.md`

마지막 프로젝트 기획서는 이번 API Gateway/HANDOFF 커밋에 포함하지 않는다.

## 작업 방식

- 사용자는 현재 일정상 Codex가 먼저 구현하고, 이후 로직·개념을 읽고 검수하는 방식을 선택했다.
- 한 번에 한 작업만 진행하고 변경 후 데이터 엔지니어 관점의 핵심 개념을 설명한다.
- 반복적인 테스트·설정 정리는 Codex가 수행한다.
- 명령에는 역할과 정상 예상 결과를 함께 설명한다.
- Windows PowerShell을 사용하며 `rg` 대신 `Get-Content`, `Get-ChildItem`, `Select-String`을 사용한다.
- 새 파일 앞에는 역할과 필요한 이유를 한국어 주석으로 남긴다.
- 테스트는 중요한 경계만 추가하고 중복 테스트와 로컬 대체 구현을 만들지 않는다.
- 사용자 변경과 dirty worktree를 보존한다.
- 개인정보나 KVKK 적용 여부를 법적 확정처럼 단정하지 않는다.

## 시작 시 읽을 파일

1. `HANDOFF.md`
2. `contracts/telemetry-event-v2.schema.json`
3. `src/pandok_ingestion/lambda_entrypoint.py`
4. `src/pandok_ingestion/handler.py`
5. `src/pandok_ingestion/pipeline.py`
6. `src/pandok_ingestion/bronze.py`
7. `src/pandok_ingestion/kinesis_producer.py`
8. `infra/ingestion_api.tf`
9. `infra/ingestion_lambda.tf`
10. `infra/streaming_kinesis.tf`
11. `infra/streaming_firehose.tf`
12. `infra/storage_s3.tf`
