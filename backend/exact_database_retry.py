"""Bounded client-side retry for exact idempotent database requests.

This module is not imported by FastAPI mutation handlers. It is an explicit
client/operator utility for repeating one exact request after PostgreSQL proves
that a transaction aborted or SQLAlchemy proves that pool checkout failed
before any connection or transaction was acquired.

Connection failures with an unknown commit outcome are never retried here.
Their recovery remains an explicit caller decision using the same idempotency
key and authoritative persisted evidence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

from sqlalchemy.exc import OperationalError, TimeoutError as SQLAlchemyTimeoutError

from backend.api.database_error_handlers import classify_database_error
from backend.database_recovery_metrics import DATABASE_RECOVERY_METRICS


T = TypeVar("T")
DatabaseHandledError = OperationalError | SQLAlchemyTimeoutError
ExactOperation = Callable[[str, int], T]
RetryObserver = Callable[["DatabaseRetryObservation"], None]
SleepFunction = Callable[[float], None]


@dataclass(frozen=True)
class ExactDatabaseRetryPolicy:
    """Finite exponential-backoff policy for exact idempotent requests."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.05
    max_delay_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.max_attempts > 20:
            raise ValueError("max_attempts must be between 1 and 20")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds cannot be negative")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds cannot be negative")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                "max_delay_seconds cannot be less than base_delay_seconds"
            )

    def delay_for_failed_attempt(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        return min(
            self.base_delay_seconds * (2 ** (attempt - 1)),
            self.max_delay_seconds,
        )


@dataclass(frozen=True)
class DatabaseRetryObservation:
    """One observable failed attempt and the policy decision that followed."""

    attempt: int
    max_attempts: int
    idempotency_key: str
    code: str
    sqlstate: Optional[str]
    retryable: bool
    retry_safe: bool
    outcome_unknown: bool
    no_transaction_started: bool
    will_retry: bool
    delay_seconds: float


class DatabaseRetryExhausted(RuntimeError, Generic[T]):
    """Raised after the final retry-safe attempt still cannot proceed."""

    def __init__(
        self,
        *,
        idempotency_key: str,
        observations: tuple[DatabaseRetryObservation, ...],
        original_error: DatabaseHandledError,
    ) -> None:
        super().__init__(
            "Database retry attempts exhausted for the exact idempotent request"
        )
        self.idempotency_key = idempotency_key
        self.observations = observations
        self.original_error = original_error


class DatabaseOutcomeUnknown(RuntimeError):
    """Explicitly preserves an ambiguous connection outcome without replay."""

    def __init__(
        self,
        *,
        idempotency_key: str,
        observation: DatabaseRetryObservation,
        original_error: OperationalError,
    ) -> None:
        super().__init__(
            "Database connection outcome is unknown; automatic retry was not performed"
        )
        self.idempotency_key = idempotency_key
        self.observation = observation
        self.original_error = original_error


def execute_exact_idempotent_database_request(
    operation: ExactOperation[T],
    *,
    idempotency_key: str,
    policy: ExactDatabaseRetryPolicy = ExactDatabaseRetryPolicy(),
    observer: Optional[RetryObserver] = None,
    sleep: SleepFunction = time.sleep,
) -> T:
    """Execute one exact request with bounded proof-aware retries.

    ``operation`` receives the unchanged idempotency key and one-based attempt
    number. Retry occurs only when ``retry_safe=true``: either a transaction was
    proven aborted, or pool checkout failed before a transaction started.
    Outcome-unknown connections raise ``DatabaseOutcomeUnknown`` immediately.
    """

    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise ValueError("idempotency_key cannot be blank")
    if normalized_key != idempotency_key:
        raise ValueError("idempotency_key must already be normalized")

    observations: list[DatabaseRetryObservation] = []
    for attempt in range(1, policy.max_attempts + 1):
        try:
            result = operation(normalized_key, attempt)
            if attempt > 1:
                DATABASE_RECOVERY_METRICS.record_retry_succeeded_after_retry()
            return result
        except (OperationalError, SQLAlchemyTimeoutError) as exc:
            detail = classify_database_error(exc)
            retry_safe = bool(detail["retry_safe"])
            outcome_unknown = bool(detail["outcome_unknown"])
            no_transaction_started = bool(
                detail.get("no_transaction_started", False)
            )
            will_retry = retry_safe and attempt < policy.max_attempts
            delay_seconds = (
                policy.delay_for_failed_attempt(attempt) if will_retry else 0.0
            )
            sqlstate_value = detail["sqlstate"]
            observation = DatabaseRetryObservation(
                attempt=attempt,
                max_attempts=policy.max_attempts,
                idempotency_key=normalized_key,
                code=str(detail["code"]),
                sqlstate=(
                    str(sqlstate_value) if sqlstate_value is not None else None
                ),
                retryable=bool(detail["retryable"]),
                retry_safe=retry_safe,
                outcome_unknown=outcome_unknown,
                no_transaction_started=no_transaction_started,
                will_retry=will_retry,
                delay_seconds=delay_seconds,
            )
            observations.append(observation)
            DATABASE_RECOVERY_METRICS.record_retry_observation(
                code=observation.code,
                sqlstate=observation.sqlstate,
                retry_safe=observation.retry_safe,
                outcome_unknown=observation.outcome_unknown,
                will_retry=observation.will_retry,
                delay_seconds=observation.delay_seconds,
                no_transaction_started=observation.no_transaction_started,
            )
            if observer is not None:
                observer(observation)

            if outcome_unknown:
                DATABASE_RECOVERY_METRICS.record_utility_outcome_unknown()
                if not isinstance(exc, OperationalError):
                    raise AssertionError(
                        "pool checkout timeout cannot produce outcome_unknown"
                    ) from exc
                raise DatabaseOutcomeUnknown(
                    idempotency_key=normalized_key,
                    observation=observation,
                    original_error=exc,
                ) from exc
            if not retry_safe:
                raise
            if not will_retry:
                DATABASE_RECOVERY_METRICS.record_retry_exhausted()
                raise DatabaseRetryExhausted(
                    idempotency_key=normalized_key,
                    observations=tuple(observations),
                    original_error=exc,
                ) from exc
            sleep(delay_seconds)

    raise AssertionError("bounded retry loop exited without result or exception")


__all__ = [
    "DatabaseOutcomeUnknown",
    "DatabaseRetryExhausted",
    "DatabaseRetryObservation",
    "ExactDatabaseRetryPolicy",
    "execute_exact_idempotent_database_request",
]
