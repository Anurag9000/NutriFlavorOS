from __future__ import annotations

import pytest

from backend.database_recovery_metrics import (
    DatabaseRecoveryAlertPolicy,
    DatabaseRecoveryMetrics,
)


def test_nonfinite_metric_delays_fail_before_counter_mutation():
    metrics = DatabaseRecoveryMetrics()

    for invalid_delay in (
        float("nan"),
        float("inf"),
        float("-inf"),
        -0.01,
        True,
        "0.1",
    ):
        with pytest.raises(ValueError, match="finite nonnegative"):
            metrics.record_retry_observation(
                code="database_transaction_retry_required",
                sqlstate="40001",
                retry_safe=True,
                outcome_unknown=False,
                will_retry=True,
                delay_seconds=invalid_delay,  # type: ignore[arg-type]
            )

    snapshot = metrics.snapshot()
    assert snapshot.retry_observation_total == 0
    assert snapshot.retry_scheduled_total == 0
    assert snapshot.retry_delay_seconds_total == 0
    assert snapshot.retry_delay_seconds_max == 0
    assert dict(snapshot.code_counts) == {}
    assert dict(snapshot.sqlstate_counts) == {}


def test_alert_thresholds_require_positive_integers():
    fields = (
        "outcome_unknown_critical_threshold",
        "retry_exhausted_warning_threshold",
        "transaction_abort_warning_threshold",
        "invalidated_connection_warning_threshold",
        "pool_timeout_warning_threshold",
    )
    for field in fields:
        for invalid_value in (0, -1, True, 1.5, "1"):
            with pytest.raises(ValueError, match="positive integer"):
                DatabaseRecoveryAlertPolicy(
                    **{field: invalid_value}  # type: ignore[arg-type]
                )


def test_exact_reviewed_classifications_remain_recordable():
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
    metrics.record_operational_error(
        code="database_pool_timeout",
        sqlstate=None,
        transaction_aborted=False,
        outcome_unknown=False,
        retryable=True,
        retry_safe=True,
        connection_invalidated=False,
        no_transaction_started=True,
    )
    metrics.record_operational_error(
        code="database_operation_failed",
        sqlstate="53300",
        transaction_aborted=False,
        outcome_unknown=False,
        retryable=False,
        retry_safe=False,
        connection_invalidated=False,
    )

    snapshot = metrics.snapshot()
    assert snapshot.operational_error_total == 4
    assert snapshot.transaction_abort_total == 1
    assert snapshot.outcome_unknown_total == 1
    assert snapshot.nonretryable_error_total == 1
    assert snapshot.invalidated_connection_total == 1
    assert dict(snapshot.code_counts) == {
        "database_transaction_retry_required": 1,
        "database_commit_outcome_unknown": 1,
        "database_pool_timeout": 1,
        "database_operation_failed": 1,
    }
    assert dict(snapshot.sqlstate_counts) == {
        "40001": 1,
        "08xxx": 1,
        "unknown": 2,
    }
