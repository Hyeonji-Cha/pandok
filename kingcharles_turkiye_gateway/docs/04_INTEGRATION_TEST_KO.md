# 04. 통합 테스트 가이드

## Test A — Valid synthetic export

Input:

`examples/aggregate-export-v1.synthetic.json`

Expected:

```text
PASS
```

## Test B — Identity field injection

예:

```json
{
  "anonymous_user_id": "..."
}
```

Expected:

```text
FAIL
```

## Test C — V2에서 제거된 session event

`event_counts` 안에:

```json
{"event_name": "session_started", "count": 1}
```

Expected:

```text
FAIL
```

## Test D — Invalid run end reason

Expected:

```text
FAIL
```

## Test E — Negative aggregate

예:

```json
{"count": -1}
```

Expected:

```text
FAIL
```

## Test F — Duplicate revision

동일한:

```text
schema_version
bucket_date
revision
source_region
```

payload를 두 번 importer에 넣습니다.

Expected:

```text
두 번째 import는 duplicate로 처리
aggregate row가 2배가 되지 않음
```

## Test G — Real export disabled

Synthetic pipeline 테스트 동안 Türkiye production exporter는 network send를 수행하면 안 됩니다.

현재 제공되는 `gateway_export/reference_exporter.py`는
JSON 파일 생성만 하며 네트워크 전송 코드를 포함하지 않습니다.
