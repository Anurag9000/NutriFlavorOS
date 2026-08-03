"""Sanitized HTTP boundary for operational database failures.

The application never retries state-changing operations inside this handler.
Callers must repeat the exact request with the same idempotency key after a
retryable transaction abort or an ambiguous connection failure.

``retryable`` means an exact client retry is the prescribed recovery action.
``retry_safe`` is narrower: it is true only when PostgreSQL proved the original
transaction aborted. Connection failures remain outcome-unknown and therefore
are not safe to reinterpret as an uncommitted mutation.
"""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError


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
    transaction_aborted = sqlstate in TRANSACTION_RETRY_SQLSTATES
    outcome_unknown = bool(
        exc.connection_invalidated
        or (sqlstate is not None and sqlstate.startswith(CONNECTION_EXCEPTION_PREFIX))
    )
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


async def database_operational_error_handler(
    _: Request,
    exc: OperationalError,
) -> JSONResponse:
    """Return a stable, non-leaking response for operational DB failures."""

    detail = classify_operational_error(exc)
    status_code = 503 if detail["retryable"] else 500
    headers = {"Retry-After": "1"} if detail["retryable"] else None
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers=headers,
    )


def install_database_error_handlers(app: FastAPI) -> None:
    """Install the operational failure boundary on one FastAPI application."""

    app.add_exception_handler(
        OperationalError,
        database_operational_error_handler,
    )


__all__ = [
    "CONNECTION_EXCEPTION_PREFIX",
    "TRANSACTION_RETRY_SQLSTATES",
    "classify_operational_error",
    "database_operational_error_handler",
    "install_database_error_handlers",
    "operational_error_sqlstate",
]
