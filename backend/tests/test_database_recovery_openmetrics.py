from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.database_recovery_metrics import DatabaseRecoveryMetricsSnapshot
from backend.database_recovery_openmetrics import (
    METRIC_PREFIX,
    render_database_recovery_openmetrics,
)


def _snapshot(
    *,
    code_counts: dict[str, int] | None = None,
    sqlstate_counts: dict[str, int] | None = None,
) -> DatabaseRecoveryMetricsSnapshot:
    return DatabaseRecoveryMetricsSnapshot(
        generated_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        operational_error_total=7,
        transaction_abort_total=4,
        outcome_unknown_total=1,
        nonretryable_error_total=2,
        retry_observation_total=6,
        retry_scheduled_total=3,
        retry_success_after_retry_total=1,
        retry_exhausted_total=1,
        utility_outcome_unknown_total=1,
        invalidated_connection_total=1,
        retry_delay_seconds_total=0.35,
        retry_delay_seconds_max=0.2,
        code_counts=(
            code_counts
            if code_counts is not None
            else {
                "database_commit_outcome_unknown": 2,
                "database_operation_failed": 2,
                "database_transaction_retry_required": 9,
            }
        ),
        sqlstate_counts=(
            sqlstate_counts
            if sqlstate_counts is not None
            else {
                "08xxx": 2,
                "40001": 5,
                "40P01": 2,
                "unknown": 4,
            }
        ),
    )


def test_openmetrics_render_is_deterministic_and_complete():
    rendered = render_database_recovery_openmetrics(_snapshot())

    assert rendered.startswith(
        "# HELP nutriflavor_database_recovery_operational_errors_total "
    )
    assert rendered.endswith("# EOF\n")
    assert rendered.count("# EOF") == 1
    assert (
        "# TYPE nutriflavor_database_recovery_retry_delay_seconds_max gauge"
        in rendered
    )
    assert (
        "nutriflavor_database_recovery_retry_success_after_retry_total 1"
        in rendered
    )
    assert (
        'nutriflavor_database_recovery_classified_events_total{code="database_commit_outcome_unknown"} 2'
        in rendered
    )
    assert (
        'nutriflavor_database_recovery_sqlstate_events_total{sqlstate="08xxx"} 2'
        in rendered
    )

    code_lines = [
        line
        for line in rendered.splitlines()
        if line.startswith(
            "nutriflavor_database_recovery_classified_events_total{"
        )
    ]
    assert code_lines == sorted(code_lines)
    sqlstate_lines = [
        line
        for line in rendered.splitlines()
        if line.startswith("nutriflavor_database_recovery_sqlstate_events_total{")
    ]
    assert sqlstate_lines == sorted(sqlstate_lines)
    assert render_database_recovery_openmetrics(_snapshot()) == rendered


def test_openmetrics_render_contains_no_domain_or_request_identifiers():
    rendered = render_database_recovery_openmetrics(_snapshot())

    forbidden = {
        "idempotency",
        "household_id",
        "user_id",
        "proposal_id",
        "schedule_id",
        "sensitive SQL",
        "request_payload",
        "food",
    }
    assert "idempotency" in forbidden
    for value in forbidden:
        assert value not in rendered
    assert METRIC_PREFIX == "nutriflavor_database_recovery"


def test_openmetrics_rejects_unbounded_error_code_label():
    with pytest.raises(ValueError, match="unbounded error-code labels"):
        render_database_recovery_openmetrics(
            _snapshot(code_counts={"tenant-specific-error": 1})
        )


def test_openmetrics_rejects_unbounded_sqlstate_label():
    with pytest.raises(ValueError, match="unbounded SQLSTATE labels"):
        render_database_recovery_openmetrics(
            _snapshot(sqlstate_counts={"23505": 1})
        )


def test_openmetrics_rejects_negative_or_nonfinite_values():
    with pytest.raises(ValueError, match="operational_error_total"):
        render_database_recovery_openmetrics(
            replace(_snapshot(), operational_error_total=-1)
        )
    with pytest.raises(ValueError, match="retry_delay_seconds_max"):
        render_database_recovery_openmetrics(
            replace(_snapshot(), retry_delay_seconds_max=float("nan"))
        )
    with pytest.raises(ValueError, match="code_counts"):
        render_database_recovery_openmetrics(
            _snapshot(code_counts={"database_operation_failed": -1})
        )
    with pytest.raises(ValueError, match="sqlstate_counts"):
        render_database_recovery_openmetrics(
            _snapshot(sqlstate_counts={"40001": True})  # type: ignore[dict-item]
        )


def test_openmetrics_empty_label_maps_remain_valid():
    rendered = render_database_recovery_openmetrics(
        _snapshot(code_counts={}, sqlstate_counts={})
    )

    assert (
        "# TYPE nutriflavor_database_recovery_classified_events_total counter"
        in rendered
    )
    assert (
        "# TYPE nutriflavor_database_recovery_sqlstate_events_total counter"
        in rendered
    )
    assert "{code=" not in rendered
    assert "{sqlstate=" not in rendered
    assert rendered.endswith("# EOF\n")
