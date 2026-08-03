"""Privacy-preserving process metrics for database recovery boundaries.

The registry stores only bounded operational classifications and aggregate
counts. It never accepts SQL text, parameters, idempotency keys, household IDs,
user IDs, proposal IDs, schedule IDs, or exception messages.

Deployments may adapt ``snapshot_database_recovery_metrics`` to their metrics
backend. The core application intentionally exposes no unauthenticated metrics
HTTP endpoint.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from types import MappingProxyType
from typing import Mapping


_ALLOWED_CODES = frozenset(
    {
        "database_transaction_retry_required",
        "database_commit_outcome_unknown",
        "database_operation_failed",
    }
)
_ALLOWED_SQLSTATES = frozenset({"40001", "40P01", "57014", "55P03"})
_UNKNOWN_SQLSTATE = "unknown"
_CONNECTION_SQLSTATE_CLASS = "08xxx"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_code(value: str) -> str:
    return value if value in _ALLOWED_CODES else "database_operation_failed"


def _safe_sqlstate(value: str | None) -> str:
    if value is None:
        return _UNKNOWN_SQLSTATE
    normalized = value.strip().upper()
    if normalized in _ALLOWED_SQLSTATES:
        return normalized
    if len(normalized) == 5 and normalized.startswith("08"):
        return _CONNECTION_SQLSTATE_CLASS
    return _UNKNOWN_SQLSTATE


@dataclass(frozen=True)
class DatabaseRecoveryAlertPolicy:
    """Process-local alert thresholds for deployment adapters."""

    outcome_unknown_critical_threshold: int = 1
    retry_exhausted_warning_threshold: int = 1
    transaction_abort_warning_threshold: int = 10
    invalidated_connection_warning_threshold: int = 1

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if value < 1:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class DatabaseRecoveryAlert:
    code: str
    severity: str
    observed: int
    threshold: int
    message: str


@dataclass(frozen=True)
class DatabaseRecoveryMetricsSnapshot:
    generated_at: datetime
    operational_error_total: int
    transaction_abort_total: int
    outcome_unknown_total: int
    nonretryable_error_total: int
    retry_observation_total: int
    retry_scheduled_total: int
    retry_exhausted_total: int
    utility_outcome_unknown_total: int
    invalidated_connection_total: int
    retry_delay_seconds_total: float
    retry_delay_seconds_max: float
    code_counts: Mapping[str, int]
    sqlstate_counts: Mapping[str, int]


class DatabaseRecoveryMetrics:
    """Thread-safe monotonic registry for sanitized database recovery metrics."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._reset_unlocked()

    def _reset_unlocked(self) -> None:
        self._operational_error_total = 0
        self._transaction_abort_total = 0
        self._outcome_unknown_total = 0
        self._nonretryable_error_total = 0
        self._retry_observation_total = 0
        self._retry_scheduled_total = 0
        self._retry_exhausted_total = 0
        self._utility_outcome_unknown_total = 0
        self._invalidated_connection_total = 0
        self._retry_delay_seconds_total = 0.0
        self._retry_delay_seconds_max = 0.0
        self._code_counts: Counter[str] = Counter()
        self._sqlstate_counts: Counter[str] = Counter()

    def reset_for_tests(self) -> None:
        """Reset process-local counters; production code must not call this."""

        with self._lock:
            self._reset_unlocked()

    def record_operational_error(
        self,
        *,
        code: str,
        sqlstate: str | None,
        transaction_aborted: bool,
        outcome_unknown: bool,
        retryable: bool,
        retry_safe: bool,
        connection_invalidated: bool,
    ) -> None:
        safe_code = _safe_code(code)
        safe_sqlstate = _safe_sqlstate(sqlstate)
        with self._lock:
            self._operational_error_total += 1
            self._code_counts[safe_code] += 1
            self._sqlstate_counts[safe_sqlstate] += 1
            if transaction_aborted:
                self._transaction_abort_total += 1
            if outcome_unknown:
                self._outcome_unknown_total += 1
            if not retryable:
                self._nonretryable_error_total += 1
            if connection_invalidated:
                self._invalidated_connection_total += 1
            if retry_safe and not transaction_aborted:
                raise ValueError("retry_safe requires a proven transaction abort")
            if outcome_unknown and retry_safe:
                raise ValueError("outcome_unknown cannot be retry_safe")

    def record_retry_observation(
        self,
        *,
        code: str,
        sqlstate: str | None,
        retry_safe: bool,
        outcome_unknown: bool,
        will_retry: bool,
        delay_seconds: float,
    ) -> None:
        if delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")
        if will_retry and not retry_safe:
            raise ValueError("will_retry requires retry_safe")
        if outcome_unknown and will_retry:
            raise ValueError("outcome_unknown cannot be automatically retried")
        safe_code = _safe_code(code)
        safe_sqlstate = _safe_sqlstate(sqlstate)
        with self._lock:
            self._retry_observation_total += 1
            self._code_counts[safe_code] += 1
            self._sqlstate_counts[safe_sqlstate] += 1
            if will_retry:
                self._retry_scheduled_total += 1
            self._retry_delay_seconds_total += delay_seconds
            self._retry_delay_seconds_max = max(
                self._retry_delay_seconds_max,
                delay_seconds,
            )

    def record_retry_exhausted(self) -> None:
        with self._lock:
            self._retry_exhausted_total += 1

    def record_utility_outcome_unknown(self) -> None:
        with self._lock:
            self._utility_outcome_unknown_total += 1

    def snapshot(self) -> DatabaseRecoveryMetricsSnapshot:
        with self._lock:
            return DatabaseRecoveryMetricsSnapshot(
                generated_at=utcnow(),
                operational_error_total=self._operational_error_total,
                transaction_abort_total=self._transaction_abort_total,
                outcome_unknown_total=self._outcome_unknown_total,
                nonretryable_error_total=self._nonretryable_error_total,
                retry_observation_total=self._retry_observation_total,
                retry_scheduled_total=self._retry_scheduled_total,
                retry_exhausted_total=self._retry_exhausted_total,
                utility_outcome_unknown_total=self._utility_outcome_unknown_total,
                invalidated_connection_total=self._invalidated_connection_total,
                retry_delay_seconds_total=self._retry_delay_seconds_total,
                retry_delay_seconds_max=self._retry_delay_seconds_max,
                code_counts=MappingProxyType(dict(self._code_counts)),
                sqlstate_counts=MappingProxyType(dict(self._sqlstate_counts)),
            )


DATABASE_RECOVERY_METRICS = DatabaseRecoveryMetrics()


def snapshot_database_recovery_metrics() -> DatabaseRecoveryMetricsSnapshot:
    return DATABASE_RECOVERY_METRICS.snapshot()


def evaluate_database_recovery_alerts(
    snapshot: DatabaseRecoveryMetricsSnapshot,
    policy: DatabaseRecoveryAlertPolicy = DatabaseRecoveryAlertPolicy(),
) -> tuple[DatabaseRecoveryAlert, ...]:
    alerts: list[DatabaseRecoveryAlert] = []
    candidates = (
        (
            "database_outcome_unknown",
            "critical",
            snapshot.outcome_unknown_total,
            policy.outcome_unknown_critical_threshold,
            "One or more database connection outcomes are ambiguous.",
        ),
        (
            "database_retry_exhausted",
            "warning",
            snapshot.retry_exhausted_total,
            policy.retry_exhausted_warning_threshold,
            "The bounded exact retry budget was exhausted.",
        ),
        (
            "database_transaction_abort_rate",
            "warning",
            snapshot.transaction_abort_total,
            policy.transaction_abort_warning_threshold,
            "Transaction abort volume reached the configured process threshold.",
        ),
        (
            "database_connection_invalidated",
            "warning",
            snapshot.invalidated_connection_total,
            policy.invalidated_connection_warning_threshold,
            "A checked-out database connection was invalidated.",
        ),
    )
    for code, severity, observed, threshold, message in candidates:
        if observed >= threshold:
            alerts.append(
                DatabaseRecoveryAlert(
                    code=code,
                    severity=severity,
                    observed=observed,
                    threshold=threshold,
                    message=message,
                )
            )
    return tuple(alerts)


__all__ = [
    "DATABASE_RECOVERY_METRICS",
    "DatabaseRecoveryAlert",
    "DatabaseRecoveryAlertPolicy",
    "DatabaseRecoveryMetrics",
    "DatabaseRecoveryMetricsSnapshot",
    "evaluate_database_recovery_alerts",
    "snapshot_database_recovery_metrics",
]
