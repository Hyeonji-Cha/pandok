# 05. Game Developer -> Data Engineer Handoff

## Data Engineer가 지금 바로 할 수 있는 일

1. schema review
2. synthetic validator
3. importer
4. aggregate Bronze
5. Silver transforms
6. Gold metrics
7. dashboard/report
8. duplicate/rejection tests

## 아직 기다려야 하는 것

Game Developer side에서 나중에 제공:

- sanitized live gateway snapshot
- 실제 DB table schema verification
- Türkiye-side exporter
- server-to-server auth
- privacy release decision
- production activation runbook

## 연결 위치

잘못된 연결:

```text
Unity -> Data Engineer AWS
```

사용하지 않습니다.

올바른 연결:

```text
Unity
 -> Türkiye Privacy Gateway
 -> Türkiye aggregate DB
 -> privacy release gate
 -> aggregate exporter
 -> Data Engineer downstream
```

따라서 downstream 변경 때문에 Steam 게임을 다시 업데이트하지 않도록
Unity와 downstream을 직접 결합하지 않습니다.
