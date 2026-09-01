# 00. 현재 상태

## 완료된 부분

### Unity / Game Client

- Gameplay Analytics는 opt-in 방식입니다.
- 동의하지 않으면 telemetry를 생성/전송하지 않습니다.
- 메인 메뉴에서 동의를 철회할 수 있습니다.
- 철회 시 새 telemetry 생성이 중단됩니다.
- pending local queue가 삭제됩니다.
- 전송 중인 sender/retry는 best-effort로 중단됩니다.
- Türkiye Gateway 실패 시 gameplay는 계속됩니다.
- Unity에는 AWS 직접 fallback 경로가 없습니다.

현재 게임에서 사용하는 핵심 이벤트:

- `session_started` — 현재 Türkiye-side transitional client flow에 존재
- `upgrade_options_shown`
- `upgrade_selected`
- `run_started`
- `run_checkpoint`
- `run_ended`

주의: PANDOK v2 anonymous AWS-bound contract에서는 `session_started`,
`anonymous_user_id`, `session_id`, client wall-clock `event_time`을 제거하는 방향입니다.
따라서 현재 Unity/Türkiye 계약과 향후 AWS-bound v2 계약을 동일한 것으로 취급하면 안 됩니다.

### Türkiye Privacy Gateway

완료된 기능:

- HTTPS ingest
- request size / field validation
- 금지 privacy field 차단
- event deduplication
- raw event payload 영구 저장 안 함
- Türkiye-local aggregate DB
- `run_checkpoint` aggregate
- `run_ended` aggregate
- 공식 run end reason 지원
- Nginx access log OFF
- Uvicorn access log OFF
- raw body log OFF
- AWS/Sydney real export OFF

## 아직 하지 않은 부분

- 실제 Türkiye -> Sydney export
- production server-to-server downstream credential
- final privacy release/suppression rule
- synthetic Türkiye -> Sydney full E2E
- Data Engineer importer
- Bronze/Silver/Gold aggregate pipeline
- production activation

## 현재 가장 중요한 규칙

**실제 플레이어 데이터의 Sydney export를 켜지 않는다.**

먼저 synthetic aggregate 데이터로 downstream 전체를 완성하고 테스트합니다.
그 후 Türkiye-side privacy release rule이 별도로 승인되어야 합니다.
