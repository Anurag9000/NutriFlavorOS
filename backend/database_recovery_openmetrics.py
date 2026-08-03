"""Deterministic OpenMetrics rendering for sanitized database recovery metrics.

This module renders an already-sanitized process snapshot. It does not expose an
HTTP endpoint, read request context, inspect exceptions, or accept domain IDs.
Deployments may publish the returned text through their own authenticated
monitoring integration.
"""

from __future__ import annotations

from backend.database_recovery_metrics import DatabaseRecoveryMetricsSnapshot


METRIC_PREFIX = "nutriflavor_database_recovery"
_ALLOWED_CODES = frozenset(
    {
        "database_transaction_retry_required",
        "database_commit_outcome_unknown",
        "database_operation_failed",
    }
)
_ALLOWED_SQLSTATES = frozenset(
    {"40001", "40P01", "57014", "55P03", "08xxx", "unknown"}
)


def _counter(
    lines: list[str],
    name: str,
    help_text: str,
    value: int | float,
) -> None:
    lines.extend(
        [
            f"# HELP {name} {help_text}",
            f"# TYPE {name} counter",
            f"{name} {value}",
        ]
    )


def _gauge(
    lines: list[str],
    name: str,
    help_text: str,
    value: int | float,
) -> None:
    lines.extend(
        [
            f"# HELP {name} {help_text}",
            f"# TYPE {name} gauge",
            f"{name} {value}",
        ]
    )


def _validate_bounded_labels(snapshot: DatabaseRecoveryMetricsSnapshot) -> None:
    unexpected_codes = set(snapshot.code_counts) - _ALLOWED_CODES
    if unexpected_codes:
        raise ValueError(
            "database recovery snapshot contains unbounded error-code labels"
        )
    unexpected_sqlstates = set(snapshot.sqlstate_counts) - _ALLOWED_SQLSTATES
    if unexpected_sqlstates:
        raise ValueError(
            "database recovery snapshot contains unbounded SQLSTATE labels"
        )


def render_database_recovery_openmetrics(
    snapshot: DatabaseRecoveryMetricsSnapshot,
) -> str:
    """Render one sanitized immutable snapshot as deterministic OpenMetrics text."""

    _validate_bounded_labels(snapshot)
    lines: list[str] = []
    scalar_counters = (
        (
            "operational_errors_total",
            "Handled operational database errors.",
            snapshot.operational_error_total,
        ),
        (
            "transaction_aborts_total",
            "Database transactions proven to have aborted.",
            snapshot.transaction_abort_total,
        ),
        (
            "outcome_unknown_total",
            "Database connection failures with ambiguous commit outcomes.",
            snapshot.outcome_unknown_total,
        ),
        (
            "nonretryable_errors_total",
            "Operational database errors not classified for exact retry.",
            snapshot.nonretryable_error_total,
        ),
        (
            "retry_observations_total",
            "Failed attempts observed by the bounded exact retry utility.",
            snapshot.retry_observation_total,
        ),
        (
            "retry_scheduled_total",
            "Retry-safe attempts for which another attempt was scheduled.",
            snapshot.retry_scheduled_total,
        ),
        (
            "retry_success_after_retry_total",
            "Exact requests that succeeded after one or more retries.",
            snapshot.retry_success_after_retry_total,
        ),
        (
            "retry_exhausted_total",
            "Exact requests that exhausted their bounded retry budget.",
            snapshot.retry_exhausted_total,
        ),
        (
            "utility_outcome_unknown_total",
            "Bounded-retry utility exits caused by ambiguous connection outcomes.",
            snapshot.utility_outcome_unknown_total,
        ),
        (
            "invalidated_connections_total",
            "Operational errors whose SQLAlchemy connection was invalidated.",
            snapshot.invalidated_connection_total,
        ),
        (
            "retry_delay_seconds_total",
            "Total delay selected by the bounded retry policy.",
            snapshot.retry_delay_seconds_total,
        ),
    )
    for suffix, help_text, value in scalar_counters:
        _counter(lines, f"{METRIC_PREFIX}_{suffix}", help_text, value)

    _gauge(
        lines,
        f"{METRIC_PREFIX}_retry_delay_seconds_max",
        "Maximum delay selected by the bounded retry policy.",
        snapshot.retry_delay_seconds_max,
    )

    code_name = f"{METRIC_PREFIX}_classified_events_total"
    lines.extend(
        [
            f"# HELP {code_name} Sanitized database recovery events by bounded code.",
            f"# TYPE {code_name} counter",
        ]
    )
    for code in sorted(snapshot.code_counts):
        lines.append(f'{code_name}{{code="{code}"}} {snapshot.code_counts[code]}')

    sqlstate_name = f"{METRIC_PREFIX}_sqlstate_events_total"
    lines.extend(
        [
            f"# HELP {sqlstate_name} Sanitized database recovery events by bounded SQLSTATE bucket.",
            f"# TYPE {sqlstate_name} counter",
        ]
    )
    for sqlstate in sorted(snapshot.sqlstate_counts):
        lines.append(
            f'{sqlstate_name}{{sqlstate="{sqlstate}"}} '
            f"{snapshot.sqlstate_counts[sqlstate]}"
        )

    lines.append("# EOF")
    return "\n".join(lines) + "\n"


__all__ = ["METRIC_PREFIX", "render_database_recovery_openmetrics"]
