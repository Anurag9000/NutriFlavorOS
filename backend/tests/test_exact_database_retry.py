from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from backend.exact_database_retry import (
    DatabaseOutcomeUnknown,
    DatabaseRetryExhausted,
    DatabaseRetryObservation,
    ExactDatabaseRetryPolicy,
    execute_exact_idempotent_database_request,
)


class _PostgresFailure(Exception):
    def __init__(self, sqlstate: str | None):
        super().__init__("driver detail must remain internal")
        self.sqlstate = sqlstate


def _error(
    sqlstate: str | None,
    *,
    connection_invalidated: bool = False,
) -> OperationalError:
    return OperationalError(
        "redacted statement",
        {},
        _PostgresFailure(sqlstate),
        connection_invalidated=connection_invalidated,
    )


def test_retry_safe_aborts_preserve_key_and_emit_bounded_observations():
    seen_operations: list[tuple[str, int]] = []
    observations: list[DatabaseRetryObservation] = []
    delays: list[float] = []

    def operation(idempotency_key: str, attempt: int) -> str:
        seen_operations.append((idempotency_key, attempt))
        if attempt < 3:
            raise _error("40001")
        return "accepted-once"

    result = execute_exact_idempotent_database_request(
        operation,
        idempotency_key="exact-client-retry-key",
        policy=ExactDatabaseRetryPolicy(
            max_attempts=4,
            base_delay_seconds=0.1,
            max_delay_seconds=0.15,
        ),
        observer=observations.append,
        sleep=delays.append,
    )

    assert result == "accepted-once"
    assert seen_operations == [
        ("exact-client-retry-key", 1),
        ("exact-client-retry-key", 2),
        ("exact-client-retry-key", 3),
    ]
    assert [value.sqlstate for value in observations] == ["40001", "40001"]
    assert [value.retry_safe for value in observations] == [True, True]
    assert [value.will_retry for value in observations] == [True, True]
    assert delays == [0.1, 0.15]


def test_retry_safe_failure_exhausts_at_exact_bound():
    attempts: list[int] = []

    def operation(_: str, attempt: int):
        attempts.append(attempt)
        raise _error("40P01")

    with pytest.raises(DatabaseRetryExhausted) as captured:
        execute_exact_idempotent_database_request(
            operation,
            idempotency_key="bounded-deadlock-key",
            policy=ExactDatabaseRetryPolicy(
                max_attempts=3,
                base_delay_seconds=0,
                max_delay_seconds=0,
            ),
            sleep=lambda _: None,
        )

    assert attempts == [1, 2, 3]
    error = captured.value
    assert error.idempotency_key == "bounded-deadlock-key"
    assert len(error.observations) == 3
    assert [value.will_retry for value in error.observations] == [True, True, False]
    assert all(value.retry_safe for value in error.observations)


def test_outcome_unknown_is_observed_but_never_automatically_retried():
    attempts: list[int] = []
    observations: list[DatabaseRetryObservation] = []
    sleeps: list[float] = []

    def operation(_: str, attempt: int):
        attempts.append(attempt)
        raise _error("08006", connection_invalidated=True)

    with pytest.raises(DatabaseOutcomeUnknown) as captured:
        execute_exact_idempotent_database_request(
            operation,
            idempotency_key="ambiguous-connection-key",
            policy=ExactDatabaseRetryPolicy(max_attempts=5),
            observer=observations.append,
            sleep=sleeps.append,
        )

    assert attempts == [1]
    assert sleeps == []
    assert len(observations) == 1
    assert observations[0].retryable is True
    assert observations[0].retry_safe is False
    assert observations[0].outcome_unknown is True
    assert observations[0].will_retry is False
    assert captured.value.idempotency_key == "ambiguous-connection-key"


def test_nonretryable_failure_is_re_raised_without_sleep():
    attempts: list[int] = []
    sleeps: list[float] = []

    def operation(_: str, attempt: int):
        attempts.append(attempt)
        raise _error("53300")

    with pytest.raises(OperationalError):
        execute_exact_idempotent_database_request(
            operation,
            idempotency_key="nonretryable-key",
            policy=ExactDatabaseRetryPolicy(max_attempts=4),
            sleep=sleeps.append,
        )

    assert attempts == [1]
    assert sleeps == []


def test_policy_and_idempotency_key_validation():
    with pytest.raises(ValueError, match="max_attempts"):
        ExactDatabaseRetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="max_delay_seconds"):
        ExactDatabaseRetryPolicy(
            base_delay_seconds=1,
            max_delay_seconds=0.5,
        )
    with pytest.raises(ValueError, match="blank"):
        execute_exact_idempotent_database_request(
            lambda _key, _attempt: "unused",
            idempotency_key="",
        )
    with pytest.raises(ValueError, match="normalized"):
        execute_exact_idempotent_database_request(
            lambda _key, _attempt: "unused",
            idempotency_key=" padded-key ",
        )
