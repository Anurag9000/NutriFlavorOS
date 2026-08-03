"""Sanitized HTTP boundary for operational database failures.

The application never retries state-changing operations inside these handlers.
Callers must repeat the exact request with the same idempotency key after a
retryable transaction abort, safe connection-pool checkout timeout, or an
ambiguous connection failure.

``retryable`` means an exact client retry is the prescribed recovery action.
``retry_safe`` is narrower: it is true only when PostgreSQL proved the original
transaction aborted or SQLAlchemy failed to acquire any connection before a
transaction started. Connection failures remain outcome-unknown.
"""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, TimeoutError as SQLAlchemyTimeoutError

from backend.database_recovery_metrics import DATABASE_RECOVERY_METRICS


TRANSACTION_RETRY_SQLSTATES: Final[frozenset[str]] = frozenset(
    {
        "40001",  # serialization_failure
        "40P01",  # deadlock_detected
        "57014",  # query_canceled, including statement_timeout
        "55P03",  # lock_not_available / lock timeout
    }
)
CONNECTION_EXCEPTION_PREFIX: Final[str] = "08"


def operational_error_sqlstate(exc: OperationalError) -> str | None:
    """Return a PostgreSQL SQLSTATE without exposing driver-specific details."""

    original = exc.orig
    direct = getattr(original, "sqlstate", None)
    if isinstance(direct, str) and direct:
        return direct
    diagnostic = getattr(original, "diag", None)
    nested = getattr(diagnostic, "sqlstate", None)
    return nested if isinstance(nested, str) and nested else None


def classify_operational_error(exc: OperationalError) -> dict[str, object]:
    """Classify retry action and proof strength for an operational failure."""

    sqlstate = operational_error_sqlstate(exc)
    raw_transaction_aborted = sqlstate in TRANSACTION_RETRY_SQLSTATES
    outcome_unknown = bool(
        exc.connection_invalidated
        or (sqlstate is not None and sqlstate.startswith(CONNECTION_EXCEPTION_PREFIX))
    )
    # Connection ambiguity dominates a nominal retry SQLSTATE. Once the
    # connection is invalidated, the caller no longer has sufficient proof that
    # the transaction outcome is safely known.
    transaction_aborted = raw_transaction_aborted and not outcome_unknown
    retryable = transaction_aborted or outcome_unknown
    retry_safe = transaction_aborted and not outcome_unknown

    if outcome_unknown:
        code = "database_commit_outcome_unknown"
        message = (
            "The database connection failed and the commit outcome is unknown. "
            "Retry the exact request with the same idempotency key."
        )
    elif transaction_aborted:
        code = "database_transaction_retry_required"
        message = (
            "The database aborted this transaction. Retry the exact request "
            "with the same idempotency key."
        )
    else:
        code = "database_operation_failed"
        message = "The database operation failed and was not automatically retried."

    return {
        "code": code,
        "message": message,
        "sqlstate": sqlstate,
        "retryable": retryable,
        "retry_safe": retry_safe,
        "transaction_aborted": transaction_aborted,
        "outcome_unknown": outcome_unknown,
        "retry_same_idempotency_key": retryable,
        "automatic_retry_performed": False,
    }


def classify_pool_timeout(_: SQLAlchemyTimeoutError) -> dict[str, object]:
    """Classify QueuePool checkout exhaustion before any transaction starts."""

    return {
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


def classify_database_error(
    exc: OperationalError | SQLAlchemyTimeoutError,
) -> dict[str, object]:
    if isinstance(exc, SQLAlchemyTimeoutError):
        return classify_pool_timeout(exc)
    return classify_operational_error(exc)


def _response_for_database_error(
    detail: dict[str, object],
    *,
    connection_invalidated: bool,
) -> JSONResponse:
    sqlstate_value = detail["sqlstate"]
    DATABASE_RECOVERY_METRICS.record_operational_error(
        code=str(detail["code"]),
        sqlstate=(str(sqlstate_value) if sqlstate_value is not None else None),
        transaction_aborted=bool(detail["transaction_aborted"]),
        outcome_unknown=bool(detail["outcome_unknown"]),
        retryable=bool(detail["retryable"]),
        retry_safe=bool(detail["retry_safe"]),
        connection_invalidated=connection_invalidated,
        no_transaction_started=bool(detail.get("no_transaction_started", False)),
    )
    status_code = 503 if detail["retryable"] else 500
    headers = {"Retry-After": "1"} if detail["retryable"] else None
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers=headers,
    )


async def database_operational_error_handler(
    _: Request,
    exc: OperationalError,
) -> JSONResponse:
    """Return a stable, non-leaking response and sanitized process metrics."""

    return _response_for_database_error(
        classify_operational_error(exc),
        connection_invalidated=bool(exc.connection_invalidated),
    )


async def database_pool_timeout_handler(
    _: Request,
    exc: SQLAlchemyTimeoutError,
) -> JSONResponse:
    """Return a retry-safe 503 for checkout exhaustion with zero DB mutation."""

    return _response_for_database_error(
        classify_pool_timeout(exc),
        connection_invalidated=False,
    )


def install_database_error_handlers(app: FastAPI) -> None:
    """Install operational and pool-timeout boundaries on one application."""

    app.add_exception_handler(
        OperationalError,
        database_operational_error_handler,
    )
    app.add_exception_handler(
        SQLAlchemyTimeoutError,
        database_pool_timeout_handler,
    )


__all__ = [
    "CONNECTION_EXCEPTION_PREFIX",
    "TRANSACTION_RETRY_SQLSTATES",
    "classify_database_error",
    "classify_operational_error",
    "classify_pool_timeout",
    "database_operational_error_handler",
    "database_pool_timeout_handler",
    "install_database_error_handlers",
    "operational_error_sqlstate",
]
