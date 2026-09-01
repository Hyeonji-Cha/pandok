# 01. 전체 작업 로드맵

이 문서는 Data Engineer가 해야 할 작업을 순서대로 설명합니다.

## Phase 1 — Contract 확인

1. `contracts/aggregate-export-v1.schema.json`을 읽습니다.
2. `examples/aggregate-export-v1.synthetic.json`을 schema로 검증합니다.
3. 필드에 player/session/run/event 식별자가 없는지 확인합니다.
4. `data_class=SYNTHETIC_TEST` 데이터만 사용합니다.

완료 조건:

```text
synthetic sample -> schema validation PASS
```

## Phase 2 — Downstream importer 작성

입력 단위는 한 개의 daily aggregate export입니다.

권장 idempotency key:

```text
(schema_version, bucket_date, revision, source_region)
```

같은 revision이 두 번 들어오면 중복 insert하지 않습니다.

Reference code:

- `reference_downstream/validate_export.py`
- `reference_downstream/import_to_sqlite.py`

처음에는 AWS 없이 local SQLite로 검증해도 됩니다.

## Phase 3 — Aggregate Bronze

King Charles 전용 downstream에서는 Bronze부터 aggregate-only로 시작합니다.

권장 테이블:

- `kc_event_counts`
- `kc_upgrade_option_counts`
- `kc_upgrade_selected_counts`
- `kc_run_checkpoint_counts`
- `kc_run_end_counts`

Bronze에 아래 데이터는 넣지 않습니다:

- raw Unity events
- request body
- event_id
- run_id
- session_id
- anonymous_user_id
- IP/header
- exact per-player timestamp

## Phase 4 — Silver

Silver에서는 다음을 수행합니다.

- type normalization
- duplicate revision 제거
- invalid bucket 차단
- aggregate consistency check
- 평균 계산용 denominator 검증

예:

```text
avg_hp_percent = hp_percent_sum / checkpoint_count
avg_final_level = final_level_sum / end_count
```

0으로 나누지 않도록 count > 0일 때만 계산합니다.

## Phase 5 — Gold

Gold는 게임 밸런싱용 aggregate metric만 생성합니다.

예:

- run end reason 비율
- 평균 run duration
- checkpoint별 평균 level / XP / HP / kill / gold
- upgrade offer count
- upgrade selection count
- offer-to-selection ratio

개별 Run 또는 개별 플레이어 검색 기능을 만들지 않습니다.

## Phase 6 — Synthetic E2E

처음에는 반드시 synthetic data만 사용합니다.

```text
Synthetic Export
    -> importer
    -> Bronze aggregate
    -> Silver
    -> Gold
    -> dashboard/report
```

다음 테스트를 수행합니다.

- 정상 sample PASS
- 동일 revision 2회 전송 -> 중복 없음
- extra identity field -> FAIL
- 잘못된 end_reason -> FAIL
- negative count -> FAIL
- schema version 불일치 -> FAIL

## Phase 7 — Türkiye Export 연결

이 단계 전까지 실제 export는 OFF입니다.

Game Developer 쪽에서 별도의 server-side exporter를 준비합니다.
Data Engineer는 Unity와 직접 연결하지 않습니다.

```text
Unity -> Türkiye Gateway -> aggregate DB -> exporter -> downstream
```

## Phase 8 — Privacy Release Gate

production export 전 별도 승인 필요:

- 어떤 aggregate cell이 해외로 나갈 수 있는지
- 작은 그룹/희귀 조합 처리 방법
- retention
- export cadence
- operational logging
- server-to-server authentication

중요:

`event_count`, `checkpoint_count`, `end_count`는 distinct contributor 수가 아닙니다.
그 값을 contributor threshold 대신 사용하면 안 됩니다.

## Phase 9 — Production

모든 synthetic E2E + privacy release test 이후에만:

```text
data_class=PRIVACY_RELEASED_PROD_AGGREGATE
```

를 허용합니다.

그 전에는 production export를 켜지 않습니다.
