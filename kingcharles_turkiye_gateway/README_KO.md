# King Charles Türkiye Gateway Handoff

> 이 폴더는 **King Charles 게임의 Türkiye Privacy Gateway 연동 전용 작업 공간**입니다.
> PANDOK 저장소의 기존 `contracts/`, `docs/`, `infra/`, `src/`, `tests/` 파일은 수정하지 않습니다.

## 현재 상태

```text
King Charles Unity Client
        |
        | HTTPS
        v
Türkiye Privacy Gateway
        |
        | Türkiye 내 검증 / 중복 제거 / 집계
        v
Türkiye Aggregate DB
        |
        | 현재 실제 해외 전송 OFF
        v
[Privacy Release Gate]
        |
        | 승인된 aggregate-only 데이터만
        v
PANDOK Downstream / AWS Sydney
```

현재 게임 클라이언트와 Türkiye Gateway 연결은 동작합니다.
실제 Türkiye -> Sydney 전송은 아직 활성화하지 않습니다.

이 폴더의 목적은 데이터 엔지니어가 **Unity 프로젝트를 수정하지 않고**
downstream 파이프라인을 준비할 수 있도록 계약, 샘플, 테스트 코드, 단계별 가이드를 제공하는 것입니다.

## 먼저 읽을 문서

1. `docs/00_STATUS_KO.md`
2. `docs/01_ROADMAP_KO.md`
3. `docs/02_DATA_ENGINEER_GUIDE_KO.md`
4. `docs/03_PRIVACY_BOUNDARY_KO.md`
5. `docs/04_INTEGRATION_TEST_KO.md`

## 절대 커밋하지 말 것

- Unity 전체 프로젝트
- 실제 플레이어/테스터 telemetry
- `aggregate.sqlite3`
- `unsent_queue.jsonl`
- ingest key
- SSH private key (`*.pem`)
- AWS credential
- TLS private key
- `.env` secret
- 실제 player/session/run/event 식별자 데이터 덤프

## 중요한 설계 결정

PANDOK의 기존 Privacy-by-Design 문서는 AWS로 전송되는 anonymous Run-level event 설계를 설명합니다.
이 King Charles 전용 폴더는 현재 구현을 더 보수적으로 운영하여
**실제 Sydney 전송을 aggregate-only로 제한하는 추가 운영 경계**를 제안합니다.

기존 PANDOK 문서는 이 폴더에서 변경하지 않습니다.
