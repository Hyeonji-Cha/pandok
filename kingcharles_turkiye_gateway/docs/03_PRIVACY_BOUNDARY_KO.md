# 03. Privacy Boundary

## 핵심 목표

Sydney에서 접근 가능한 데이터만으로 다음을 할 수 없어야 합니다.

- Steam 계정 식별
- 사람 식별
- device/install 식별
- player IP 확인
- 서로 다른 Run을 같은 플레이어로 연결

## PANDOK 기존 v2 방향과의 관계

기존 PANDOK Privacy-by-Design 방향은 다음을 제거합니다.

- `session_started`
- `anonymous_user_id`
- `session_id`
- client wall-clock `event_time`

그리고 Run 내부에서만 사용하는:

- random `run_id`
- random `event_id`
- `event_sequence`
- relative elapsed time

을 사용하도록 설계되어 있습니다.

King Charles 전용 operational handoff는 여기에 추가로
**실제 Sydney 전달을 aggregate-only로 제한**하는 더 보수적인 경계를 사용합니다.

이 폴더는 기존 PANDOK privacy 문서를 수정하지 않습니다.

## Aggregate Export v1 금지 데이터

다음 key/value는 export에 포함되면 안 됩니다.

```text
anonymous_user_id
session_id
run_id
event_id
choice_id
steam_id
player_id
user_id
account_id
device_id
installation_id
hardware_id
ip
ip_address
x_forwarded_for
event_time
exact player timestamp
raw request body
```

Schema는 `additionalProperties: false`를 사용하여 예상하지 못한 필드를 거부합니다.

## 실제 production blocker

현재 aggregate count만으로는 distinct contributor 수를 알 수 없습니다.

따라서 아래처럼 하면 안 됩니다.

```text
end_count >= 10
=> 10명의 다른 사람이다
```

이는 보장되지 않습니다.

실제 export 전에 별도 privacy release 방법을 설계하고 승인해야 합니다.
그 전까지 synthetic E2E만 수행합니다.
