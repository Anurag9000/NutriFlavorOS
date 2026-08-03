from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from backend.api.database_error_handlers import (
    classify_database_error,
    classify_pool_timeout,
    install_database_error_handlers,
)
from backend.database_recovery_metrics import (
    DATABASE_RECOVERY_METRICS,
    DatabaseRecoveryAlertPolicy,
    evaluate_database_recovery_alerts,
)
from backend.database_recovery_openmetrics import (
    render_database_recovery_openmetrics,
)
from backend.exact_database_retry import (
    DatabaseRetryExhausted,
    DatabaseRetryObservation,
    ExactDatabaseRetryPolicy,
    execute_exact_idempotent_database_request,
)


def _timeout() -> SQLAlchemyTimeoutError:
    return SQLAlchemyTimeoutError(
        "QueuePool limit reached; request details must not escape"
    )


def _client_for(error: SQLAlchemyTimeoutError) -> TestClient:
    app = FastAPI()
    install_database_error_handlers(app)

    @app.post("/mutation")
    def fail():
        raise error

    return TestClient(app)


def setup_function() -> None:
    DATABASE_RECOVERY_METRICS.reset_for_tests()


def test_pool_timeout_returns_retry_safe_structured_503():
    error = _timeout()
    detail = classify_pool_timeout(error)

    assert classify_database_error(error) == detail
    assert detail == {
        "code": "database_pool_timeout",
        "message": (
            "The database connection pool was exhausted before this operation "
            "acquired a connection. Retry the exact request with the same "
            "idempotency key."
        ),
        "sqlstate": None,
        "retryable": True,
        "retry_safe": True,
        "transaction_aborted": False,
        "no_transaction_started": True,
        "outcome_unknown": False,
        "failure_stage": "connection_checkout",
        "retry_same_idempotency_key": True,
        "automatic_retry_performed": False,
    }

    response = _client_for(error).post("/mutation")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
    assert response.json()["detail"] == detail
    assert "QueuePool limit" not in response.text
    assert "request details" not in response.text

    snapshot = DATABASE_RECOVERY_METRICS.snapshot()
    assert snapshot.operational_error_total == 1
    assert snapshot.transaction_abort_total == 0
    assert snapshot.outcome_unknown_total == 0
    assert snapshot.nonretryable_error_total == 0
    assert snapshot.code_counts == {"database_pool_timeout": 1}
    assert snapshot.sqlstate_counts == {"unknown": 1}


def test_bounded_utility_retries_pool_timeout_with_same_key():
    attempts: list[tuple[str, int]] = []
    observations: list[DatabaseRetryObservation] = []
    delays: list[float] = []

    def operation(key: str, attempt: int) -> str:
        attempts.append((key, attempt))
        if attempt == 1:
            raise _timeout()
        return "accepted-once"

    result = execute_exact_idempotent_database_request(
        operation,
        idempotency_key="pool-timeout-exact-key",
        policy=ExactDatabaseRetryPolicy(
            max_attempts=2,
            base_delay_seconds=0.125,
            max_delay_seconds=0.125,
        ),
        observer=observations.append,
        sleep=delays.append,
    )

    assert result == "accepted-once"
    assert attempts == [
        ("pool-timeout-exact-key", 1),
        ("pool-timeout-exact-key", 2),
    ]
    assert len(observations) == 1
    observation = observations[0]
    assert observation.code == "database_pool_timeout"
    assert observation.sqlstate is None
    assert observation.retryable is True
    assert observation.retry_safe is True
    assert observation.no_transaction_started is True
    assert observation.outcome_unknown is False
    assert observation.will_retry is True
    assert observation.delay_seconds == 0.125
    assert delays == [0.125]

    snapshot = DATABASE_RECOVERY_METRICS.snapshot()
    assert snapshot.retry_observation_total == 1
    assert snapshot.retry_scheduled_total == 1
    assert snapshot.retry_success_after_retry_total == 1
    assert snapshot.retry_exhausted_total == 0
    assert snapshot.code_counts == {"database_pool_timeout": 1}


def test_pool_timeout_exhaustion_is_bounded_and_observable():
    attempts: list[int] = []

    def operation(_: str, attempt: int):
        attempts.append(attempt)
        raise _timeout()

    with pytest.raises(DatabaseRetryExhausted) as captured:
        execute_exact_idempotent_database_request(
            operation,
            idempotency_key="pool-timeout-exhausted-key",
            policy=ExactDatabaseRetryPolicy(
                max_attempts=2,
                base_delay_seconds=0,
                max_delay_seconds=0,
            ),
            sleep=lambda _: None,
        )

    assert attempts == [1, 2]
    assert captured.value.idempotency_key == "pool-timeout-exhausted-key"
    assert [value.code for value in captured.value.observations] == [
        "database_pool_timeout",
        "database_pool_timeout",
    ]
    assert all(
        value.no_transaction_started for value in captured.value.observations
    )
    assert [value.will_retry for value in captured.value.observations] == [
        True,
        False,
    ]

    snapshot = DATABASE_RECOVERY_METRICS.snapshot()
    assert snapshot.retry_observation_total == 2
    assert snapshot.retry_scheduled_total == 1
    assert snapshot.retry_exhausted_total == 1
    assert snapshot.code_counts == {"database_pool_timeout": 2}


def test_pool_timeout_alert_and_openmetrics_are_bounded():
    DATABASE_RECOVERY_METRICS.record_operational_error(
        code="database_pool_timeout",
        sqlstate=None,
        transaction_aborted=False,
        outcome_unknown=False,
        retryable=True,
        retry_safe=True,
        connection_invalidated=False,
        no_transaction_started=True,
    )
    snapshot = DATABASE_RECOVERY_METRICS.snapshot()
    alerts = evaluate_database_recovery_alerts(
        snapshot,
        DatabaseRecoveryAlertPolicy(
            outcome_unknown_critical_threshold=2,
            retry_exhausted_warning_threshold=2,
            transaction_abort_warning_threshold=2,
            invalidated_connection_warning_threshold=2,
            pool_timeout_warning_threshold=1,
        ),
    )

    assert [(value.code, value.severity, value.observed) for value in alerts] == [
        ("database_pool_timeout", "warning", 1)
    ]
    rendered = render_database_recovery_openmetrics(snapshot)
    assert (
        'nutriflavor_database_recovery_classified_events_total{code="database_pool_timeout"} 1'
        in rendered
    )
    assert "QueuePool" not in rendered
    assert "pool-timeout-exact-key" not in rendered
    assert snapshot.generated_at <= datetime.now(timezone.utc)
