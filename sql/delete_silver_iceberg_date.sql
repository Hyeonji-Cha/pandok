-- 지정한 날짜의 기존 Iceberg Silver 행을 제거한다.
-- 동일 날짜 backfill에서 이전 결과와 새 결과가 중복되는 것을 막기 위해 필요하다.

DELETE FROM pandok_dev.silver_events_iceberg
WHERE received_date = '__RECEIVED_DATE__';