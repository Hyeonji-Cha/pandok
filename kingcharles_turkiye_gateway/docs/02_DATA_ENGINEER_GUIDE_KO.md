# 02. Data Engineer 작업 가이드

## 내가 받아야 하는 것

Data Engineer가 필요한 것은 Unity 프로젝트 전체가 아닙니다.

필요한 것:

- 이 폴더
- Aggregate Export v1 schema
- synthetic example
- Türkiye-side exporter endpoint/spec (나중 단계)
- server-to-server authentication 정보 (production 직전 별도 전달)

필요하지 않은 것:

- Unity scene/prefab
- Steam SDK 설정
- Unity ingest key
- player local queue
- SSH private key
- Türkiye aggregate SQLite 원본
- 실제 tester raw telemetry

## Step 1 — 로컬 검증

repo root에서:

```powershell
uv run python .\kingcharles_turkiye_gateway\reference_downstream\validate_export.py `
  .\kingcharles_turkiye_gateway\examples\aggregate-export-v1.synthetic.json
```

예상 결과:

```text
VALID: aggregate-export-v1
```

## Step 2 — contract tests

```powershell
uv run pytest .\kingcharles_turkiye_gateway\tests -q
```

예상:

```text
all tests passed
```

## Step 3 — reference importer 실행

```powershell
uv run python .\kingcharles_turkiye_gateway\reference_downstream\import_to_sqlite.py `
  .\kingcharles_turkiye_gateway\examples\aggregate-export-v1.synthetic.json `
  .\kingcharles_turkiye_gateway\reference_downstream\downstream_demo.sqlite3
```

이 코드는 production 코드가 아니라 importer 동작 예시입니다.

## Step 4 — 실제 downstream 구현

아래 원칙을 유지하면서 AWS/Sydney 쪽 ingestion을 구현합니다.

- schema validation first
- fail closed
- idempotent revision import
- aggregate-only
- unexpected property reject
- raw body logging 금지
- identity field 금지

## Step 5 — Bronze/Silver/Gold

처음부터 aggregate table을 사용합니다.

PANDOK 기존 repository의 executable pipeline을 바로 변경하지 마세요.
King Charles 연결은 이 전용 폴더에서 먼저 독립적으로 검증한 뒤
필요한 변경이 생기면 팀 review 후 별도 PR로 진행합니다.

## Step 6 — production 전 확인 질문

Game Developer에게 아래 항목이 준비되었는지 확인합니다.

1. Türkiye exporter가 synthetic payload를 생성하는가?
2. production export flag는 아직 OFF인가?
3. privacy release rule이 승인되었는가?
4. exporter 인증은 client key와 분리된 server-to-server credential인가?
5. log에 raw body / ID / IP가 없는가?
6. duplicate delivery가 idempotent한가?
7. retention이 정해졌는가?

하나라도 불명확하면 실제 production export를 활성화하지 않습니다.
