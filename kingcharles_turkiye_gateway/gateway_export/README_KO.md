# Gateway Export 코드 상태

`reference_exporter.py`는 **production sender가 아닙니다.**

현재 목적:

- Türkiye aggregate SQLite -> Aggregate Export v1 JSON 변환 형태를 보여줌
- 네트워크 전송 없음
- real Sydney export를 켜지 않음
- live DB schema 확인 전 배포 금지

다음 Game Developer 작업에서 실제 서버의 table schema를 read-only로 확인한 뒤
이 파일의 query를 live schema와 맞춥니다.

특히 `upgrade_selected_counts`의 실제 table 이름/column은
server에서 확인하기 전까지 가정하지 않습니다.
