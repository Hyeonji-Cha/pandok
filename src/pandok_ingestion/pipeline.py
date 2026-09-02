# Türkiye Gateway에서 받은 v2 이벤트를 검증한 후 Bronze 레코드로 변환한다.
# 계약을 위반한 이벤트가 AWS에 저장되는 것을 차단하기 위해 필요하다.
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, cast

from pandok_contracts import (
    ValidationIssue,
    validate_anonymous_event,
)

from .bronze import build_bronze_record


class EventContractError(ValueError):
    """Represent an event rejected by the telemetry contract."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        message = "; ".join(
            f"{issue.code.value}: {issue.message}"
            for issue in self.issues
        )
        super().__init__(message)


def prepare_bronze_record(
    event: Any,
    ingestion_channel: str,
    *,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    """Validate an event before building its Bronze record."""
    # AWS Bronze에 저장하기 전에 익명 v2 계약과 개인정보 제거 규칙을 검증한다.
    issues = validate_anonymous_event(event)

    if issues:
        raise EventContractError(issues)

    validated_event = cast(Mapping[str, Any], event)

    return build_bronze_record(
        validated_event,
        ingestion_channel,
        received_at=received_at,
    )
