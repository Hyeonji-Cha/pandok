# HANDOFF

이 문서는 다른 데스크톱의 Codex가 PANDOK의 Privacy-by-Design 재설계를 중복 조사 없이 이어가기 위한 인수인계 문서다.
현재 구현 상태, 확정된 결정, 미완료 작업, 개발자 의존사항과 작업 방식을 한곳에 기록한다.

## 프로젝트 목표

Steam 정식 게임 **King Charles: Rise of the Alpha**의 동의 기반 gameplay telemetry를 수집하고,
중복·누락·지연 가능성이 있는 이벤트를 신뢰할 수 있는 Bronze, Silver, Gold 데이터로 변환해
게임 개선 지표와 검증 가능한 LLM 리포트를 만드는 데이터 엔지니어링 프로젝트다.

익명성 재설계 이후의 핵심 목표는 다음과 같다.

> AWS Sydney와 한국 데이터 엔지니어가 접근하는 영역에는 플레이어를 직접 또는 간접적으로
> 식별하거나 서로 다른 Run을 같은 플레이어의 것으로 연결할 수 있는 데이터를 보내지 않는다.

이 설계가 KVKK 적용 제외를 보장한다고 단정하지 않는다. 실제 privacy 특성은 Unity 구현,
Türkiye VPS 업체, 로그·백업 설정, 네트워크 경로와 향후 Schema 변경에 따라 다시 검토해야 한다.

## 저장소와 현재 Git 상태

- 실제 저장소: `C:\Users\NT551_11TH\Desktop\workspace\pandok`
- GitHub: `https://github.com/Hyeonji-Cha/pandok.git`
- 현재 브랜치: `main`
- 마지막 Privacy 구현 커밋: `d2419a5 feat(privacy): expand anonymous telemetry field guards`
- 이 문서는 바로 다음 `docs: add project handoff` 커밋으로 추가된다.
- 다른 데스크톱에서는 실제 HEAD와 원격 동기화 상태를 `git status`와 `git log`로 다시 확인한다.

정상이면 `git status`에서 다음과 유사하게 표시된다.

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

## 최종 Privacy Architecture 기준

```text
King Charles Game Client
        |
        | HTTPS
        v
Türkiye Anonymization Gateway
  Nginx TLS termination
        |
  FastAPI Privacy Gateway
  - JSON Schema validation
  - allowed-field reconstruction
  - forbidden-field detection
  - incoming-header removal
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
        -> Airflow
        -> Gold aggregate metrics
        -> LLM report
```

Game Client가 AWS Sydney에 직접 연결하는 경로와 Gateway 장애 시 AWS 직접 fallback은 금지한다.
Gateway 장애가 gameplay를 중단해서도 안 된다.

## 현재까지 확정된 익명성 결정

- `anonymous_user_id`를 v2에서 제거한다.
- `session_id`를 v2에서 제거한다.
- AWS-bound v2에서는 `session_started` 이벤트를 제거한다.
- Steam ID, 닉네임, 계정·기기·설치·하드웨어 ID, IP, 인증정보와 영구 fingerprint를 수집하지 않는다.
- 영구 UUID를 사용하지 않지만 UUID 자체를 전부 금지하지는 않는다.
- `run_id`는 매 Run 시작 시 새 random UUID로 생성하고 다른 Run이나 player와 매핑하지 않는다.
- `event_id`는 논리 이벤트마다 새 random UUID로 만들고 동일 이벤트 재전송에서는 그대로 유지한다.
- `choice_id`는 한 Run 안의 shown/selected 연결에만 사용한다.
- 서로 다른 Run이 같은 플레이어의 것인지 AWS에서 알아낼 수 없어야 한다.
- 클라이언트의 정확한 wall-clock `event_time`은 v2 payload에서 제거한다.
- `event_sequence`는 Run 내부 논리 순서를 표현한다.
- `run_elapsed_seconds`는 Run 내부 gameplay 상대시간을 표현한다.
- Gateway 수신시간은 client payload와 분리된 운영 metadata로 다루며 필요한 최소 정밀도와 보존기간을 추후 확정한다.
- Product 데이터의 정확한 시각 분석은 포기한다.
- 정확한 Watermark·Late Event 재현은 `CONTROLLED_SCENARIO` 합성 데이터로 검증할 수 있다.
- Sequence 번호 공백은 Run 폐기 오류가 아니라 `INCOMPLETE` 상태로 처리한다.
- 같은 Sequence 번호에 서로 다른 이벤트가 있으면 `INVALID`다.
- `run_elapsed_seconds`는 감소할 수 없지만 서로 같은 값은 허용한다.
- Initial weapon shown/selected는 `run_started`보다 앞설 수 있으며 모두 elapsed 0을 사용한다.
- 실제 사용자 데이터는 `CONSENTED_PROD_PLAY`, 기능 검증은 `CONTROLLED_SCENARIO`, 부하는 `LOAD_TEST`로 분리한다.
- Gold와 LLM 입력에는 실제 제품 분석용 집계만 전달하며 개별 player 추적을 만들지 않는다.
- AWS telemetry 보존 상한 기본값은 30일이다.

## 의도적으로 포기한 분석

- 동일 player의 장기 행동 추적
- 개인별 retention과 재방문 분석
- 특정 사용자의 history
- user-level cross-Run 분석
- 특정 사용자의 과거 Run 검색과 개별 삭제
- 실제 사용자별 DAU 계산
- 정확한 실제 플레이 시각과 시간대별 이용 패턴

## 계속 유지하는 분석

- Run duration과 survival time
- death timing, cause, level
- kill, XP, HP, gold progression
- upgrade shown, selected, pick rate, level, rarity, combination
- pickup과 enemy/miniboss encounter
- checkpoint 누락과 Run 완전성
- 문제 gameplay 구간과 balance anomaly
- Gold 집계 지표와 근거 기반 LLM 개선안

## Türkiye Gateway 필수 조건

Türkiye VPS는 데이터 엔지니어가 대신 만들거나 소유하지 않는다. 게임 운영자인 개발자가 직접
업체를 선택하고 자기 계정으로 서버를 생성하며 계약·결제·소유권을 관리한다.

VPS와 Gateway 요구사항:

- 실제 물리 서버 위치: Türkiye
- 업체의 로그·백업·subprocessor 저장 위치 확인
- Nginx access log: 기본 `OFF` 또는 개인정보 없는 최소 형식
- Request body logging: `OFF`
- Player IP application log: `OFF`
- IP 보관이 보안상 불가피하면 Türkiye 내부에서 최소 기간만 보관하고 gameplay event와 연결 금지
- 불필요한 backup/snapshot: `OFF`
- 외부 Analytics/APM: 기본 `OFF`
- 해외 CDN 또는 client traffic proxy: 사용하지 않음
- `X-Forwarded-For`, `Forwarded`, `X-Real-IP`, `CF-Connecting-IP`, `True-Client-IP`를 AWS로 전달하지 않음
- Incoming request를 그대로 proxy하지 않고 허용된 payload와 header로 새로운 outbound request 생성
- AWS에서 보이는 source network identity는 player가 아니라 Türkiye Gateway여야 함
- Game Client에 AWS endpoint나 AWS credential을 넣지 않음

## 역할 분담

| 작업 | 담당 |
|---|---|
| Unity/Game telemetry event 생성과 전송 제어 | 게임 개발자 |
| Türkiye VPS 업체·계정·서버·비용 관리 | 게임 개발자 |
| Game에 Türkiye Gateway endpoint 연결 | 게임 개발자 + 데이터 엔지니어 |
| Nginx와 FastAPI Privacy Gateway 구현 | 데이터 엔지니어 |
| 익명 Schema와 금지 필드 검사 | 데이터 엔지니어 |
| AWS Sydney 수집 파이프라인과 2차 privacy validation | 데이터 엔지니어 |
| 실제 Build의 동의·Queue·전송 검증 | 공동 |

개발자 답변을 기다리는 항목:

1. 요구조건을 만족하는 Türkiye VPS를 개발자 명의로 생성할 수 있는지
2. 기존 PANDOK v1 Schema가 Unity에 어느 정도 구현됐는지
3. 과거 요청한 `anonymous_user_id`와 `session_id`가 이미 구현됐다면 계정·기기 ID와 연결되는지
4. 실제 게임의 content ID 허용 목록
5. Game endpoint를 Türkiye Gateway 하나로 제한하고 direct AWS fallback을 끌 수 있는지

개발자 답변을 기다리는 동안 합성 데이터, Schema, Validator, Gateway local test와 AWS mock은 계속 구현할 수 있다.

## 구현 완료

### v1 기존 기준

- JSON Schema Draft 2020-12 이벤트 계약
- `session_started`, `upgrade_options_shown`, `upgrade_selected`, `run_started`, `run_checkpoint`, `run_ended`
- 단일 이벤트와 전체 Run 순서 검증
- `event_id` 중복·충돌 검증
- shown/selected 연결과 checkpoint 검증
- 개인정보 금지 필드 검사
- CLI와 정상·오류 Fixture
- v1 CONTROLLED_SCENARIO Generator
- JSON ingestion handler, contract validation, Bronze wrapper
- Generator → JSON → ingestion → Bronze local E2E test

v1은 비교와 회귀 검증을 위해 유지한다. v2 확정 전 임의 삭제하지 않는다.

### Privacy 설계 문서

- `docs/privacy-by-design.md`: 활성 개인정보 경계와 재설계 단계
- `docs/privacy-field-review.md`: 모든 현재 필드의 `KEEP / MODIFY / REMOVE` 분류
- `docs/privacy-threat-model.md`: 식별 위험, 차단 방법, 검증 테스트와 잔여 위험
- `docs/architecture.md`: 기존 direct Steam-to-AWS 흐름은 구현 금지라는 경고가 상단에 있음

### v2 익명 계약

- `contracts/telemetry-event-v2.schema.json`
- v2에서는 다섯 Run 이벤트만 지원하고 `session_started`는 제외
- 공통 필드:
  - `event_id`
  - `event_name`
  - `source_type`
  - `run_id`
  - `event_sequence`
  - `run_elapsed_seconds`
  - `game_version`
  - `schema_version = 2.0`
- `anonymous_user_id`, `session_id`, `event_time`이 들어오면 거부
- 콘텐츠 문자열 길이와 upgrade 배열 크기 제한
- 정상 Run과 privacy-invalid Fixture 추가

### v2 Validator

- `validate_anonymous_event()` 구현
- `validate_anonymous_sequence()` 구현
- `SequenceStatus`: `VALID`, `INCOMPLETE`, `INVALID`
- 도착 순서와 관계없이 `event_sequence`로 재구성
- 동일 재시도 허용
- Sequence 공백과 `run_ended` 미도착은 `INCOMPLETE`
- Sequence 충돌, elapsed 감소, Run 상관관계 불일치, 종료 이후 이벤트는 `INVALID`
- 기존 v1 `validate_event()`와 `validate_sequence()`는 유지

### Terraform과 S3

- Terraform은 `infra/` 바로 아래에 구성하며 중복 하위 Terraform 폴더를 만들지 않는다.
- AWS Region은 Sydney `ap-southeast-2`로 validation되어 있다.
- `bronze_retention_days` 기본값은 30일이다.
- `infra/storage_s3.tf`에 다음 구성이 커밋되어 있다.
  - Bronze S3 bucket prefix
  - dev에서만 `force_destroy`
  - Public Access Block
  - `BucketOwnerEnforced`
  - 추가 KMS 비용이 없는 SSE-S3 `AES256`
  - 30일 lifecycle과 7일 incomplete multipart cleanup
  - HTTPS-only bucket policy
- `terraform init`, `fmt`, `validate`는 이전에 통과했다.
- 아직 `terraform apply`는 하지 않았다.
- Privacy Architecture가 확정될 때까지 Terraform 리소스 확장을 중단한다.

## 마지막 완료 작업

마지막 완료 작업은 **v2 개인정보 금지 필드 확장**이다.

변경 파일:

- `src/pandok_contracts/validator.py`
  - v1 금지 목록을 그대로 보존
  - v2 전용 금지 목록 추가
  - 계정·기기·설치·네트워크·인증·위치·영구 ID 관련 키 차단
  - snake_case, camelCase, 대소문자와 구분자 차이를 정규화
  - 중첩 객체와 배열을 재귀 검사
- `tests/contract/test_privacy_rules.py`
  - 27개 금지 키 표기 변형 테스트
  - 중첩 field 테스트
  - `player_level`, `run_id`, `event_sequence` 과잉 차단 방지
  - 일반 미승인 필드는 `schema_invalid`로 구분
  - v1 `session_id` 회귀 방지

마지막 실행 결과:

```text
Privacy/v2 tests: 51 passed
Full test suite:   158 passed
```

재검증 명령:

```powershell
uv run pytest tests/contract/test_privacy_rules.py tests/contract/test_anonymous_event_contract_v2.py -q
uv run pytest -q
```

정상이면 각각 `51 passed`, 전체 `158 passed`가 예상된다. 테스트 수는 이후 테스트가 추가되면 증가할 수 있다.

## 다음 작업

### 1. v2 CONTROLLED_SCENARIO Generator

개발자 데이터 없이 다음 파이프라인 작업을 검증하기 위한 첫 구현이다.

- 기존 `src/pandok_producer/generator.py`와 `tests/producer/test_generator.py`를 재사용한다.
- 새 Python 파일을 만들지 않는다.
- v1 Generator는 유지한다.
- v2 Generator는 다음만 새로 생성한다.
  - Run마다 새 `run_id`
  - 이벤트마다 새 `event_id`
  - choice마다 새 `choice_id`
- `event_sequence`, `run_elapsed_seconds`, gameplay 값은 검증된 template 의미를 유지한다.
- `anonymous_user_id`, `session_id`, client `event_time`을 생성하지 않는다.
- 생성 직후 `validate_anonymous_sequence()` 결과가 `VALID`인지 확인한다.
- retry fixture는 동일 `event_id`, `event_sequence`, payload를 유지한다.

### 2. v2 Ingestion과 Bronze envelope

- 기존 handler/pipeline/bronze 파일을 재사용한다.
- v2 payload를 `validate_anonymous_event()`로 검증한다.
- Production ingestion channel을 `unity_client` 직접 경로가 아니라 인증된 `turkiye_gateway`로 변경한다.
- Bronze는 두 privacy gate를 통과한 익명 이벤트만 저장한다.
- `metadata.received_at`의 정밀도·용도·30일 보존을 명시적으로 결정한다.
- v1 local tests는 유지한다.

### 3. Türkiye Gateway local implementation

- 개발자가 VPS를 만들기 전까지 로컬 FastAPI로 구현·테스트한다.
- Pydantic/JSON Schema allow-list validation
- unknown field와 forbidden field fail-closed 차단
- 원본 request/header forwarding 금지
- 허용 payload로 새 outbound request 생성
- AWS endpoint 대신 mock receiver 사용
- IP, body, auth token을 로그에 남기지 않음

### 4. Gateway Privacy Tests

- `X-Forwarded-For`, `Forwarded`, `X-Real-IP`, `CF-Connecting-IP`, `True-Client-IP` 제거
- raw headers와 request body가 outbound/log에 없음
- privacy-invalid 요청은 outbound 호출 0회
- valid v2 요청만 새 outbound payload로 전달

### 5. Lambda Privacy Validator local implementation

- Gateway와 독립된 2차 v2 Schema/forbidden-field 검증
- invalid 요청은 Kinesis write 0회
- valid 요청만 mock Kinesis에 기록
- raw request/event logging 금지

### 6. Local anonymous E2E

```text
v2 Generator
→ FastAPI Privacy Gateway
→ Lambda Privacy Validator
→ mock Kinesis
→ anonymous Bronze record
```

### 7. Architecture 승인 후 Terraform 재개

- API Gateway authentication 방식
- Secrets/SSM 사용 여부
- throttling, Lambda concurrency, CloudWatch retention
- Kinesis/Flink/Firehose/S3 경로
- 모든 리소스에 비용 기본값과 상한 validation 적용
- AWS 리소스 생성 전 비용과 삭제 방법 설명

## 현재 알려진 미완료 또는 불일치

- CLI는 아직 v1 `validate-event`와 `validate-sequence`만 사용한다.
- v2 Validator는 Python API로 구현됐지만 CLI version routing은 아직 없다.
- 기존 ingestion과 Bronze wrapper는 아직 v1 검증을 사용한다.
- 기존 v1 Generator는 `anonymous_user_id`, `session_id`, `event_time`을 생성한다.
- 일반 game content ID는 아직 실제 allow-list가 없고 길이·문자 패턴만 제한한다.
- `metadata.received_at`은 현재 millisecond 정밀도다.
- README의 Supported P0 events 표는 v1 여섯 이벤트를 보여주며 v2 다섯 이벤트 구분을 아직 추가하지 않았다.
- `docs/architecture.md` 본문에는 이전 direct flow가 남아 있지만 상단에 구현 금지 경고가 있다.
- Türkiye VPS provider와 Gateway-to-AWS 인증 방식은 미확정이다.
- 실제 Unity payload와 네트워크 evidence는 개발자 작업 대기 상태다.

## 비용 및 AWS 원칙

- AWS Region: `ap-southeast-2`
- 운영 확장 가능한 구조를 유지하되 dev 기본값은 저비용이어야 한다.
- Terraform validation으로 과도한 설정을 배포 전에 막는다.
- S3 lifecycle, CloudWatch retention, 실패 레코드 보존기간을 명시한다.
- Lambda reserved concurrency, API throttling, Kinesis mode와 로그량에 상한을 둔다.
- NAT Gateway, MWAA와 기타 고정비가 큰 서비스는 설명과 승인 없이 생성하지 않는다.
- AWS Budget은 비용 감시 수단이며 실시간 결제 차단 장치로 설명하지 않는다.
- 실제 가격은 구현 시점의 Sydney 공식 요금을 다시 확인한다.
- Commit 또는 Terraform code가 존재한다고 AWS 리소스가 생성된 것은 아니다. `apply` 여부를 반드시 확인한다.

## 작업 방식과 사용자 선호

- 사용자가 명시적으로 **“수정”**이라고 말할 때만 Codex가 파일을 수정한다.
- 사용자가 “시작하자”, “해줘”, “가자”, “다음”이라고만 하면 다음 한 작업의 계획과 이유를 설명한다.
- 한 번에 한 작업만 진행한다.
- 사용자가 학습해야 하는 핵심 구현은 먼저 설명하고, 반복 작업은 Codex가 수행 범위를 알린 뒤 처리한다.
- 명령어를 줄 때 명령의 역할과 정상 결과를 함께 설명한다.
- Windows PowerShell 명령을 사용한다.
- 이 환경에는 `rg`가 없으므로 확인 명령에 `rg`를 제시하지 않는다. `Get-ChildItem`, `Select-String`, `Get-Content`를 사용한다.
- 새 파일 맨 앞에는 파일 역할과 필요한 이유를 이해하기 쉬운 한국어 주석으로 남긴다. JSON은 주석 문법이 없으므로 `$comment`를 사용한다.
- 개발자와 공유하는 계약 설명·문서는 영어를 우선하고, 사용자 학습용 코드 역할 주석은 한국어를 사용한다.
- 함수마다 모든 줄을 설명하지 말고 역할과 핵심 결정만 한국어 주석으로 남긴다.
- 파일 증식을 피하고 기존 파일을 재사용할 수 있으면 재사용한다.
- 테스트 파일은 경계가 명확히 다른 경우에만 새로 만들고 기존 테스트에 추가할 수 있으면 추가한다.
- 기존 사용자 변경과 dirty worktree를 보존한다.
- Commit과 push는 사용자가 요청할 때만 실행한다.
- 적절한 commit 시점과 권장 commit message를 작업 완료 시 알려준다.
- 개인정보·법률 문제에 대해 “아무 문제 없다”, “KVKK 제외 확정”처럼 단정하지 않는다.

## 주요 문서

- `README.md`
- `docs/privacy-by-design.md`
- `docs/privacy-field-review.md`
- `docs/privacy-threat-model.md`
- `docs/architecture.md`
- `docs/project-scope.md`
- `docs/event-contract.md`
- `docs/event-data-model.md`
- `docs/unity-telemetry-integration-plan.md`
- `contracts/telemetry-event-v1.schema.json`
- `contracts/telemetry-event-v2.schema.json`

새 데스크톱의 Codex는 먼저 `HANDOFF.md`, `git status`, 최근 commit, 위 Privacy 문서와 v2 Schema를 읽고
현재 상태를 확인한 다음 작업해야 한다. 과거의 direct Game-to-AWS 구조를 활성 설계로 오해하지 말아야 한다.
