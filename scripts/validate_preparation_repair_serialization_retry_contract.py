#!/usr/bin/env python3
"""Validate bounded exact retry after repeated PostgreSQL serialization aborts."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "handler": "backend/api/database_error_handlers.py",
    "utility": "backend/exact_database_retry.py",
    "unit_tests": "backend/tests/test_exact_database_retry.py",
    "postgres_test": (
        "backend/tests/test_preparation_repair_serialization_retry_postgres.py"
    ),
    "repair_workflow": ".github/workflows/preparation-repair.yml",
    "postgres_workflow": ".github/workflows/preparation-repair-postgres.yml",
    "docs": "docs/PREPARATION_REPAIR_SERIALIZATION_RETRY.md",
    "acceptance_docs": "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing serialization-retry file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def _test_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "handler": {
            '"40001"',
            "retry_safe = transaction_aborted and not outcome_unknown",
            '"automatic_retry_performed": False',
        },
        "utility": {
            "class ExactDatabaseRetryPolicy",
            "max_attempts: int = 3",
            "base_delay_seconds: float = 0.05",
            "max_delay_seconds: float = 1.0",
            "class DatabaseRetryObservation",
            "class DatabaseRetryExhausted",
            "class DatabaseOutcomeUnknown",
            "def execute_exact_idempotent_database_request",
            "normalized_key = idempotency_key.strip()",
            "for attempt in range(1, policy.max_attempts + 1)",
            "classify_operational_error(exc)",
            "will_retry = retry_safe and attempt < policy.max_attempts",
            "observer(observation)",
            "sleep(delay_seconds)",
            "if outcome_unknown:",
            "raise DatabaseOutcomeUnknown(",
            "raise DatabaseRetryExhausted(",
        },
        "unit_tests": {
            "test_retry_safe_aborts_preserve_key_and_emit_bounded_observations",
            "test_retry_safe_failure_exhausts_at_exact_bound",
            "test_outcome_unknown_is_observed_but_never_automatically_retried",
            "test_nonretryable_failure_is_re_raised_without_sleep",
            "test_policy_and_idempotency_key_validation",
            'delays == [0.1, 0.15]',
            "attempts == [1, 2, 3]",
            "attempts == [1]",
        },
        "postgres_test": {
            "test_postgres_repeated_serialization_failures_retry_exact_request_once",
            'isolation_level="SERIALIZABLE"',
            'text("SELECT version FROM households WHERE id = :household_id")',
            '"SET version = version + 1, updated_at = NOW() "',
            "failed_attempts = 3",
            "max_attempts=4",
            '"40001"',
            "all(value.retry_safe is True for value in observations)",
            "all(value.will_retry is True for value in observations)",
            "accept_repair_proposal_with_source_guard(",
            '"acceptances": 1',
            '"replacement_schedules": 1',
            '"proposal_accepted_events": 1',
            '"replacement_created_events": 1',
            'assert [value.event_type for value in proposal_events] == [',
            '"created",',
            '"accepted",',
        },
        "repair_workflow": {
            "backend/exact_database_retry.py",
            "backend/tests/test_exact_database_retry.py",
            "validate_preparation_repair_serialization_retry_contract.py",
        },
        "postgres_workflow": {
            "test_preparation_repair_serialization_retry_postgres.py",
            "validate_preparation_repair_serialization_retry_contract.py",
        },
        "docs": {
            "Bounded Exact Serialization Retry",
            "SERIALIZABLE",
            "SQLSTATE `40001`",
            "same idempotency key",
            "max_attempts",
            "DatabaseOutcomeUnknown",
            "automatic_retry_performed=false",
        },
        "acceptance_docs": {
            "Repeated serialization recovery",
            "three consecutive SQLSTATE `40001`",
            "fourth exact-key attempt",
        },
        "status": {
            "bounded exact serialization retry",
            "three consecutive `40001` aborts",
        },
        "roadmap": {
            "bounded exact serialization retry",
            "three consecutive `40001` aborts",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks serialization-retry fragment: {fragment}"
                )

    expected_unit_tests = {
        "test_retry_safe_aborts_preserve_key_and_emit_bounded_observations",
        "test_retry_safe_failure_exhausts_at_exact_bound",
        "test_outcome_unknown_is_observed_but_never_automatically_retried",
        "test_nonretryable_failure_is_re_raised_without_sleep",
        "test_policy_and_idempotency_key_validation",
    }
    missing_unit_tests = expected_unit_tests - _test_names(sources["unit_tests"])
    for name in sorted(missing_unit_tests):
        errors.append(f"bounded retry unit test is missing: {name}")

    if (
        "test_postgres_repeated_serialization_failures_retry_exact_request_once"
        not in _test_names(sources["postgres_test"])
    ):
        errors.append("real PostgreSQL repeated-serialization test is missing")

    forbidden_utility = {
        "while True",
        "session.commit(",
        "db.commit(",
        "accept_repair_proposal",
        "time.sleep(1",
    }
    for fragment in sorted(forbidden_utility):
        if fragment in sources["utility"]:
            errors.append(
                "bounded retry utility contains forbidden mutation or unbounded action: "
                f"{fragment}"
            )

    forbidden_postgres_test = {
        "raise OperationalError(",
        "monkeypatch",
        "network_or_failover_simulated",
    }
    for fragment in sorted(forbidden_postgres_test):
        if fragment in sources["postgres_test"]:
            errors.append(
                "serialization test fabricates the database abort: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "database": "postgresql",
        "isolation": "serializable",
        "sqlstate": "40001",
        "forced_abort_count": 3,
        "maximum_attempts": 4,
        "exact_same_key_required": True,
        "bounded_client_retry": True,
        "server_automatic_retry": False,
        "outcome_unknown_automatic_retry": False,
        "observer_required": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "ast_validated": True,
        "source_formatting_normalized": True,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
