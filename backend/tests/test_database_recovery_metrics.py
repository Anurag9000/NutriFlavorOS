from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.api.database_error_handlers import install_database_error_handlers
from backend.database_recovery_metrics import (
    DATABASE_RECOVERY_METRICS,
    DatabaseRecoveryAlertPolicy,
    DatabaseRecoveryMetrics,
    evaluate_database_recovery_alerts,
    snapshot_database_recovery_metrics,
)
from backend.exact_database_retry import (
    DatabaseOutcomeUnknown,
    DatabaseRetryExhausted,
    ExactDatabaseRetryPolicy,
    execute_exact_idempotent_database_request,
)


class _PostgresFailure(Exception):
    def __init__(self, sqlstate: str | None):
        super().__init__("sensitive driver message")
        self.sqlstate = sqlstate


def _error(
    sqlstate: str | None,
    *,
    connection_invalidated: bool = False,
) -> OperationalError:
    return OperationalError(
        "sensitive SQL statement",
        {"secret": "must-not-escape"},
        _PostgresFailure(sqlstate),
        connection_invalidated=connection_invalidated,
    )


@pytest.fixture(autouse=True)
def reset_global_metrics():
    DATABASE_RECOVERY_METRICS.reset_for_tests()
    yield
    DATABASE_RECOVERY_METRICS.reset_for_tests()


def test_metrics_snapshot_sanitizes_labels_and_is_immutable():
    metrics = DatabaseRecoveryMetrics()
    metrics.record_operational_error(
        code="unknown-internal-code",
        sqlstate="99999",
        transaction_aborted=False,
        outcome_unknown=False,
        retryable=False,
        retry_safe=False,
        connection_invalidated=False,
    )
    metrics.record_operational_error(
        code="database_commit_outcome_unknown",
        sqlstate="08006",
        transaction_aborted=False,
        outcome_unknown=True,
        retryable=True,
        retry_safe=False,
        connection_invalidated=True,
    )

    snapshot = metrics.snapshot()
    assert snapshot.operational_error_total == 2
    assert snapshot.nonretryable_error_total == 1
    assert snapshot.outcome_unknown_total == 1
    assert snapshot.invalidated_connection_total == 1
    assert dict(snapshot.code_counts) == {
        "database_operation_failed": 1,
        "database_commit_outcome_unknown": 1,
    }
    assert dict(snapshot.sqlstate_counts) == {
        "unknown": 1,
        "08xxx": 1,
    }
    with pytest.raises(TypeError):
        snapshot.code_counts["new"] = 1  # type: ignore[index]

    rendered = repr(snapshot)
    assert "sensitive" not in rendered
    assert "must-not-escape" not in rendered
    assert "99999" not in rendered
    assert "08006" not in rendered


def test_http_error_handler_records_only_sanitized_classification():
    app = FastAPI()
    install_database_error_handlers(app)

    @app.get("/failure")
    def fail():
        raise _error("08006", connection_invalidated=True)

    response = TestClient(app).get("/failure")
    assert response.status_code == 503

    snapshot = snapshot_database_recovery_metrics()
    assert snapshot.operational_error_total == 1
    assert snapshot.outcome_unknown_total == 1
    assert snapshot.invalidated_connection_total == 1
    assert snapshot.transaction_abort_total == 0
    assert dict(snapshot.code_counts) == {
        "database_commit_outcome_unknown": 1,
    }
    assert dict(snapshot.sqlstate_counts) == {"08xxx": 1}
    rendered = repr(snapshot)
    assert "sensitive SQL statement" not in rendered
    assert "must-not-escape" not in rendered


def test_bounded_retry_metrics_track_convergence_exhaustion_and_ambiguity():
    success_attempts: list[int] = []

    def eventually_succeeds(_: str, attempt: int) -> str:
        success_attempts.append(attempt)
        if attempt == 1:
            raise _error("40001")
        return "accepted"

    result = execute_exact_idempotent_database_request(
        eventually_succeeds,
        idempotency_key="metrics-success-key",
        policy=ExactDatabaseRetryPolicy(
            max_attempts=2,
            base_delay_seconds=0,
            max_delay_seconds=0,
        ),
        sleep=lambda _: None,
    )
    assert result == "accepted"
    assert success_attempts == [1, 2]

    with pytest.raises(DatabaseRetryExhausted):
        execute_exact_idempotent_database_request(
            lambda _key, _attempt: (_ for _ in ()).throw(_error("40P01")),
            idempotency_key="metrics-exhausted-key",
            policy=ExactDatabaseRetryPolicy(
                max_attempts=2,
                base_delay_seconds=0,
                max_delay_seconds=0,
            ),
            sleep=lambda _: None,
        )

    with pytest.raises(DatabaseOutcomeUnknown):
        execute_exact_idempotent_database_request(
            lambda _key, _attempt: (_ for _ in ()).throw(
                _error("08006", connection_invalidated=True)
            ),
            idempotency_key="metrics-outcome-unknown-key",
            policy=ExactDatabaseRetryPolicy(max_attempts=5),
            sleep=lambda _: None,
        )

    snapshot = snapshot_database_recovery_metrics()
    assert snapshot.retry_observation_total == 4
    assert snapshot.retry_scheduled_total == 2
    assert snapshot.retry_success_after_retry_total == 1
    assert snapshot.retry_exhausted_total == 1
    assert snapshot.utility_outcome_unknown_total == 1
    assert snapshot.retry_delay_seconds_total == 0
    assert snapshot.retry_delay_seconds_max == 0
    assert dict(snapshot.sqlstate_counts) == {
        "40001": 1,
        "40P01": 2,
        "08xxx": 1,
    }
    rendered = repr(snapshot)
    assert "metrics-success-key" not in rendered
    assert "metrics-exhausted-key" not in rendered
    assert "metrics-outcome-unknown-key" not in rendered


def test_alert_evaluation_uses_explicit_thresholds():
    metrics = DatabaseRecoveryMetrics()
    metrics.record_operational_error(
        code="database_transaction_retry_required",
        sqlstate="40001",
        transaction_aborted=True,
        outcome_unknown=False,
        retryable=True,
        retry_safe=True,
        connection_invalidated=False,
    )
    metrics.record_operational_error(
        code="database_commit_outcome_unknown",
        sqlstate="08006",
        transaction_aborted=False,
        outcome_unknown=True,
        retryable=True,
        retry_safe=False,
        connection_invalidated=True,
    )
    metrics.record_retry_exhausted()

    alerts = evaluate_database_recovery_alerts(
        metrics.snapshot(),
        DatabaseRecoveryAlertPolicy(
            outcome_unknown_critical_threshold=1,
            retry_exhausted_warning_threshold=1,
            transaction_abort_warning_threshold=1,
            invalidated_connection_warning_threshold=1,
        ),
    )
    assert [(value.code, value.severity) for value in alerts] == [
        ("database_outcome_unknown", "critical"),
        ("database_retry_exhausted", "warning"),
        ("database_transaction_abort_rate", "warning"),
        ("database_connection_invalidated", "warning"),
    ]
    assert all(value.observed >= value.threshold for value in alerts)


def test_metrics_registry_is_thread_safe_and_monotonic():
    metrics = DatabaseRecoveryMetrics()

    def record_batch(_: int) -> None:
        for _index in range(200):
            metrics.record_retry_observation(
                code="database_transaction_retry_required",
                sqlstate="40001",
                retry_safe=True,
                outcome_unknown=False,
                will_retry=True,
                delay_seconds=0.01,
            )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(record_batch, range(8)))

    snapshot = metrics.snapshot()
    assert snapshot.retry_observation_total == 1600
    assert snapshot.retry_scheduled_total == 1600
    assert snapshot.retry_delay_seconds_total == pytest.approx(16.0)
    assert snapshot.retry_delay_seconds_max == pytest.approx(0.01)
    assert dict(snapshot.code_counts) == {
        "database_transaction_retry_required": 1600,
    }
    assert dict(snapshot.sqlstate_counts) == {"40001": 1600}


def test_invalid_metric_combinations_fail_before_counter_mutation():
    metrics = DatabaseRecoveryMetrics()
    with pytest.raises(ValueError, match="retry_safe"):
        metrics.record_operational_error(
            code="database_transaction_retry_required",
            sqlstate="40001",
            transaction_aborted=False,
            outcome_unknown=False,
            retryable=True,
            retry_safe=True,
            connection_invalidated=False,
        )
    with pytest.raises(ValueError, match="will_retry"):
        metrics.record_retry_observation(
            code="database_commit_outcome_unknown",
            sqlstate="08006",
            retry_safe=False,
            outcome_unknown=True,
            will_retry=True,
            delay_seconds=0,
        )

    snapshot = metrics.snapshot()
    assert snapshot.operational_error_total == 0
    assert snapshot.retry_observation_total == 0
