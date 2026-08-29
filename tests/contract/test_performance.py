from __future__ import annotations

from time import perf_counter

from pandok_contracts.validator import validate_event


def test_ten_thousand_events_validate_in_under_ten_seconds(valid_sequence):
    event = valid_sequence[0]
    started = perf_counter()
    for _ in range(10_000):
        assert validate_event(event) == []
    elapsed = perf_counter() - started
    assert elapsed < 10, f"10,000 validations took {elapsed:.2f}s"
