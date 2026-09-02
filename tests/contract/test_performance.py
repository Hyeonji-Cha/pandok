from __future__ import annotations

from time import perf_counter

from pandok_contracts.validator import validate_anonymous_event


def test_ten_thousand_events_validate_in_under_ten_seconds(
    anonymous_sequence,
):
    event = next(
        item
        for item in anonymous_sequence
        if item["event_name"] == "run_started"
    )
    started = perf_counter()
    for _ in range(10_000):
        assert validate_anonymous_event(event) == []
    elapsed = perf_counter() - started
    assert elapsed < 10, f"10,000 validations took {elapsed:.2f}s"
