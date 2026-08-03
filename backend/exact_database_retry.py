"""Bounded client-side retry for proven-aborted database transactions.

This module is not imported by the FastAPI mutation handlers. It is an explicit
client/operator utility for repeating one exact idempotent request after
PostgreSQL proves that the previous transaction aborted.

Connection failures with an unknown commit outcome are never retried here.
Their recovery remains an explicit caller decision using the same idempotency
key and the authoritative service idempotency record.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

from sqlalchemy.exc import OperationalError

from backend.api.database_error_handlers import classify_operational_error


T = TypeVar("T")
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
    will_retry: bool
    delay_seconds: float


class DatabaseRetryExhausted(RuntimeError, Generic[T]):
    """Raised after the final retry-safe attempt still aborts."""

    def __init__(
        self,
        *,
        idempotency_key: str,
        observations: tuple[DatabaseRetryObservation, ...],
        original_error: OperationalError,
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
    """Execute one exact request with bounded retry-safe transaction retries.

    ``operation`` receives the unchanged idempotency key and the one-based
    attempt number. Only failures classified as ``transaction_aborted`` and
    ``retry_safe`` are retried. Outcome-unknown connections raise
    ``DatabaseOutcomeUnknown`` immediately. No server-side mutation handler is
    called automatically outside the caller-supplied operation.
    """

    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise ValueError("idempotency_key cannot be blank")
    if normalized_key != idempotency_key:
        raise ValueError("idempotency_key must already be normalized")

    observations: list[DatabaseRetryObservation] = []
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation(normalized_key, attempt)
        except OperationalError as exc:
            detail = classify_operational_error(exc)
            retry_safe = bool(detail["retry_safe"])
            outcome_unknown = bool(detail["outcome_unknown"])
            will_retry = retry_safe and attempt < policy.max_attempts
            delay_seconds = (
                policy.delay_for_failed_attempt(attempt) if will_retry else 0.0
            )
            observation = DatabaseRetryObservation(
                attempt=attempt,
                max_attempts=policy.max_attempts,
                idempotency_key=normalized_key,
                code=str(detail["code"]),
                sqlstate=(
                    str(detail["sqlstate"])
                    if detail["sqlstate"] is not None
                    else None
                ),
                retryable=bool(detail["retryable"]),
                retry_safe=retry_safe,
                outcome_unknown=outcome_unknown,
                will_retry=will_retry,
                delay_seconds=delay_seconds,
            )
            observations.append(observation)
            if observer is not None:
                observer(observation)

            if outcome_unknown:
                raise DatabaseOutcomeUnknown(
                    idempotency_key=normalized_key,
                    observation=observation,
                    original_error=exc,
                ) from exc
            if not retry_safe:
                raise
            if not will_retry:
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
