# 미리 만든 정상 이벤트 예시를 복사해 실행마다 UUID와 발생 시각을 새로 만든다.
# Unity 없이 수집 파이프라인을 반복 검증할 CONTROLLED_SCENARIO 데이터를 만들기 위해 사용한다.
# Bronze 포장은 수집 계층에 맡겨 실제 Unity처럼 원본 이벤트만 공급하기 위해 사용한다.

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pandok_contracts import ValidationIssue, validate_sequence


# 생성 전후 계약 검증에서 발견된 오류들을 하나의 예외로 전달한다.
# 호출부가 오류 코드 목록을 확인하고 생성 실패 원인을 기록할 수 있게 한다.
class ScenarioGenerationError(ValueError):
    """Represent a controlled scenario that violates the event contract."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        # 여러 검증 오류를 변경 불가능한 형태로 예외 안에 보관한다.
        self.issues = tuple(issues)

        # 로그에서 오류 코드와 내용을 한 번에 확인할 수 있도록 문자열로 합친다.
        message = "; ".join(
            f"{issue.code.value}: {issue.message}"
            for issue in self.issues
        )
        super().__init__(message)


# JSON의 UTC 표기인 Z를 Python이 처리할 수 있는 UTC 오프셋으로 변환한다.
def _parse_event_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# 모든 시각을 UTC로 통일하고 JSON 표준에서 사용하는 Z 표기로 반환한다.
def _format_event_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def generate_controlled_sequence(
    template_events: Sequence[Mapping[str, Any]],
    *,
    started_at: datetime | None = None,
    uuid_factory: Callable[[], UUID] = uuid4,
) -> list[dict[str, Any]]:
    """Create one contract-valid controlled P0 sequence from a template."""
    # 같은 템플릿을 반복 사용해도 원본 fixture가 변경되지 않도록 복사한다.
    generated_events = deepcopy(
        [dict(event) for event in template_events]
    )

    # 잘못된 템플릿을 기반으로 새로운 이벤트가 생성되는 것을 먼저 차단한다.
    template_issues = validate_sequence(generated_events)
    if template_issues:
        raise ScenarioGenerationError(template_issues)

    if started_at is None:
        started_at = datetime.now(UTC)
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ValueError("started_at must be timezone-aware")
    started_at = started_at.astimezone(UTC)

    first_event_time = min(
        _parse_event_time(str(event["event_time"]))
        for event in generated_events
    )
    anonymous_user_id = str(uuid_factory())
    session_id = str(uuid_factory())
    run_id = str(uuid_factory())
    choice_ids: dict[str, str] = {}

    # 게임 플레이 값은 유지하고 실행마다 달라져야 하는 ID와 시각만 교체한다.
    for event in generated_events:
        original_event_time = _parse_event_time(str(event["event_time"]))
        event["event_id"] = str(uuid_factory())
        event["event_time"] = _format_event_time(
            started_at + (original_event_time - first_event_time)
        )
        event["source_type"] = "CONTROLLED_SCENARIO"
        event["anonymous_user_id"] = anonymous_user_id
        event["session_id"] = session_id

        if event.get("run_id") is not None:
            event["run_id"] = run_id

        original_choice_id = event.get("choice_id")
        if isinstance(original_choice_id, str):
            if original_choice_id not in choice_ids:
                choice_ids[original_choice_id] = str(uuid_factory())
            event["choice_id"] = choice_ids[original_choice_id]

    # 값 교체 과정에서 이벤트 순서와 shown-selected 연결이 깨지지 않았는지 확인한다.
    generated_issues = validate_sequence(generated_events)
    if generated_issues:
        raise ScenarioGenerationError(generated_issues)

    return generated_events
