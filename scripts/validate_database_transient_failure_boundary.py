#!/usr/bin/env python3
"""Validate structured PostgreSQL timeout/deadlock recovery boundaries."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "handler": "backend/api/database_error_handlers.py",
    "main": "backend/main.py",
    "unit_tests": "backend/tests/test_database_operational_error_handler.py",
    "postgres_tests": "backend/tests/test_preparation_repair_transient_failures_postgres.py",
    "postgres_workflow": ".github/workflows/preparation-repair-postgres.yml",
    "repair_workflow": ".github/workflows/preparation-repair.yml",
    "docs": "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing transient-failure boundary file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "handler": {
            '"40001"',
            '"40P01"',
            '"57014"',
            '"55P03"',
            'CONNECTION_EXCEPTION_PREFIX: Final[str] = "08"',
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            "retry_safe = transaction_aborted and not outcome_unknown",
            '"retry_safe": retry_safe',
            "retry_same_idempotency_key",
            '"automatic_retry_performed": False',
            'headers = {"Retry-After": "1"}',
            "def install_database_error_handlers",
        },
        "main": {
            "database_error_handlers",
            "database_error_handlers.install_database_error_handlers(app)",
        },
        "unit_tests": {
            "test_deadlock_returns_retryable_structured_503",
            "test_statement_timeout_uses_same_exact_retry_boundary",
            "test_connection_exception_marks_commit_outcome_unknown",
            "test_invalidated_connection_without_sqlstate_is_ambiguous",
            "test_nonretryable_operational_error_is_sanitized_500",
            '"retry_safe": True',
            'assert detail["retry_safe"] is False',
            'assert "driver details" not in response.text',
        },
        "postgres_tests": {
            "test_postgres_statement_timeout_rolls_back_then_exact_retry_succeeds",
            "SET LOCAL statement_timeout = '150ms'",
            '"sqlstate": "57014"',
            "test_postgres_deadlock_victim_then_exact_retry_converges_once",
            "SET LOCAL deadlock_timeout = '100ms'",
            'value.get("sqlstate") == "40P01"',
            "_assert_one_accepted_replacement",
            'event_types == ["created", "accepted"]',
        },
        "postgres_workflow": {
            "test_preparation_repair_transient_failures_postgres.py",
            "validate_database_transient_failure_boundary.py",
        },
        "repair_workflow": {
            "database_error_handlers.py",
            "test_database_operational_error_handler.py",
            "validate_database_transient_failure_boundary.py",
        },
        "docs": {
            "Statement timeout and deadlock recovery",
            "same idempotency key",
            "no automatic retry",
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks transient-failure fragment: {fragment}")

    forbidden_handler = {
        "time.sleep(",
        "while True",
        "session.commit(",
        "db.commit(",
        "retry_operation(",
    }
    for fragment in sorted(forbidden_handler):
        if fragment in sources["handler"]:
            errors.append(f"database error handler performs forbidden retry action: {fragment}")

    return {
        "valid": not errors,
        "transaction_retry_sqlstates": ["40001", "40P01", "55P03", "57014"],
        "ambiguous_connection_prefix": "08",
        "transaction_abort_retry_safe": True,
        "connection_outcome_retry_safe": False,
        "automatic_retry_performed": False,
        "exact_same_key_retry_required": True,
        "real_postgres_statement_timeout": True,
        "real_postgres_deadlock": True,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
