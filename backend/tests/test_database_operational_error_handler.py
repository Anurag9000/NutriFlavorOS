from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.api.database_error_handlers import (
    classify_operational_error,
    install_database_error_handlers,
    operational_error_sqlstate,
)


class _PostgresFailure(Exception):
    def __init__(self, message: str, sqlstate: str | None = None):
        super().__init__(message)
        self.sqlstate = sqlstate


def _operational_error(
    sqlstate: str | None,
    *,
    connection_invalidated: bool = False,
) -> OperationalError:
    return OperationalError(
        "SELECT redacted",
        {},
        _PostgresFailure("driver details must not escape", sqlstate),
        connection_invalidated=connection_invalidated,
    )


def _client_for(error: OperationalError) -> TestClient:
    app = FastAPI()
    install_database_error_handlers(app)

    @app.get("/failure")
    def fail():
        raise error

    return TestClient(app)


def test_deadlock_returns_retryable_structured_503():
    error = _operational_error("40P01")
    response = _client_for(error).get("/failure")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
    detail = response.json()["detail"]
    assert detail == {
        "code": "database_transaction_retry_required",
        "message": (
            "The database aborted this transaction. Retry the exact request "
            "with the same idempotency key."
        ),
        "sqlstate": "40P01",
        "retryable": True,
        "transaction_aborted": True,
        "outcome_unknown": False,
        "retry_same_idempotency_key": True,
        "automatic_retry_performed": False,
    }
    assert "driver details" not in response.text


def test_statement_timeout_uses_same_exact_retry_boundary():
    detail = classify_operational_error(_operational_error("57014"))

    assert detail["code"] == "database_transaction_retry_required"
    assert detail["transaction_aborted"] is True
    assert detail["outcome_unknown"] is False
    assert detail["retry_same_idempotency_key"] is True
    assert detail["automatic_retry_performed"] is False


def test_connection_exception_marks_commit_outcome_unknown():
    response = _client_for(_operational_error("08006")).get("/failure")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "database_commit_outcome_unknown"
    assert detail["retryable"] is True
    assert detail["transaction_aborted"] is False
    assert detail["outcome_unknown"] is True
    assert detail["retry_same_idempotency_key"] is True
    assert detail["automatic_retry_performed"] is False


def test_invalidated_connection_without_sqlstate_is_ambiguous():
    error = _operational_error(None, connection_invalidated=True)

    assert operational_error_sqlstate(error) is None
    detail = classify_operational_error(error)
    assert detail["code"] == "database_commit_outcome_unknown"
    assert detail["outcome_unknown"] is True
    assert detail["retryable"] is True


def test_nonretryable_operational_error_is_sanitized_500():
    response = _client_for(_operational_error("53300")).get("/failure")

    assert response.status_code == 500
    assert "retry-after" not in response.headers
    detail = response.json()["detail"]
    assert detail["code"] == "database_operation_failed"
    assert detail["sqlstate"] == "53300"
    assert detail["retryable"] is False
    assert detail["transaction_aborted"] is False
    assert detail["outcome_unknown"] is False
    assert detail["retry_same_idempotency_key"] is False
    assert detail["automatic_retry_performed"] is False
    assert "SELECT redacted" not in response.text
    assert "driver details" not in response.text
