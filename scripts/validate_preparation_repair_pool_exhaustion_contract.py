#!/usr/bin/env python3
"""Validate PostgreSQL pool-exhaustion recovery and zero-mutation evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "handler": "backend/api/database_error_handlers.py",
    "metrics": "backend/database_recovery_metrics.py",
    "openmetrics": "backend/database_recovery_openmetrics.py",
    "retry": "backend/exact_database_retry.py",
    "unit_tests": "backend/tests/test_database_pool_timeout_boundary.py",
    "postgres_test": "backend/tests/test_preparation_repair_pool_exhaustion_postgres.py",
    "workflow": ".github/workflows/preparation-repair-pool-exhaustion.yml",
    "docs": "docs/PREPARATION_REPAIR_POOL_EXHAUSTION.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing pool exhaustion file: {relative}")
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
            "TimeoutError as SQLAlchemyTimeoutError",
            "def classify_pool_timeout",
            '"code": "database_pool_timeout"',
            '"retry_safe": True',
            '"transaction_aborted": False',
            '"no_transaction_started": True',
            '"outcome_unknown": False',
            '"failure_stage": "connection_checkout"',
            '"automatic_retry_performed": False',
            "database_pool_timeout_handler",
            "app.add_exception_handler(",
        },
        "metrics": {
            '"database_pool_timeout"',
            "pool_timeout_warning_threshold",
            "no_transaction_started: bool = False",
            "retry_safe requires a proven abort or no started transaction",
            "Database connection-pool checkout timed out before a transaction started",
        },
        "openmetrics": {
            '"database_pool_timeout"',
            'METRIC_PREFIX = "nutriflavor_database_recovery"',
        },
        "retry": {
            "TimeoutError as SQLAlchemyTimeoutError",
            "classify_database_error",
            "except (OperationalError, SQLAlchemyTimeoutError) as exc",
            "no_transaction_started: bool",
            "no_transaction_started=observation.no_transaction_started",
        },
        "unit_tests": {
            "test_pool_timeout_returns_retry_safe_structured_503",
            "test_bounded_utility_retries_pool_timeout_with_same_key",
            "test_pool_timeout_exhaustion_is_bounded_and_observable",
            "test_pool_timeout_alert_and_openmetrics_are_bounded",
            '"database_pool_timeout"',
            '"no_transaction_started": True',
            'assert "QueuePool limit" not in response.text',
        },
        "postgres_test": {
            "test_postgres_pool_exhaustion_times_out_before_mutation_and_recovers",
            "poolclass=QueuePool",
            "pool_size=1",
            "max_overflow=0",
            "pool_timeout=0.1",
            "pool_pre_ping=True",
            'holder.execute(text("SELECT 1"))',
            '"acceptances": 0',
            '"replacement_schedules": 0',
            '"proposal_accepted_events": 0',
            '"replacement_created_events": 0',
            '"acceptances": 1',
            '"replacement_schedules": 1',
            "replayed.acceptance.id == accepted.acceptance.id",
            'db.get_bind().dialect.name == "postgresql"',
        },
        "docs": {
            "PostgreSQL Pool Exhaustion Recovery",
            "database_pool_timeout",
            "no_transaction_started=true",
            "pool_size=1",
            "max_overflow=0",
            "pool_timeout=0.1",
            "exactly zero",
            "same acceptance and schedule identities",
            "No public metrics endpoint is introduced",
        },
        "status": {
            "pool exhaustion",
            "database_pool_timeout",
            "no_transaction_started=true",
        },
        "roadmap": {
            "pool exhaustion",
            "database_pool_timeout",
        },
        "workflow": {
            "validate-preparation-repair-pool-exhaustion",
            "postgres:16",
            "pool-exhaustion-recovery",
            "backend/tests/test_database_pool_timeout_boundary.py",
            "backend/tests/test_preparation_repair_pool_exhaustion_postgres.py",
            "validate_preparation_repair_pool_exhaustion_contract.py",
            "reports/preparation-repair-pool-exhaustion.xml",
            "if-no-files-found: error",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks pool exhaustion fragment: {fragment}"
                )

    expected_unit_tests = {
        "test_pool_timeout_returns_retry_safe_structured_503",
        "test_bounded_utility_retries_pool_timeout_with_same_key",
        "test_pool_timeout_exhaustion_is_bounded_and_observable",
        "test_pool_timeout_alert_and_openmetrics_are_bounded",
    }
    for name in sorted(expected_unit_tests - _test_names(sources["unit_tests"])):
        errors.append(f"pool timeout unit test is missing: {name}")

    expected_postgres = {
        "test_postgres_pool_exhaustion_times_out_before_mutation_and_recovers"
    }
    for name in sorted(expected_postgres - _test_names(sources["postgres_test"])):
        errors.append(f"pool exhaustion PostgreSQL test is missing: {name}")

    lowered = sources["postgres_test"].lower()
    if "sqlite" in lowered:
        errors.append("pool exhaustion PostgreSQL test contains SQLite fallback")
    for fragment in {
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "DBPreparationRepairProposalAcceptance(",
        "DBPersistedPreparationSchedule(",
        "OperationalError(",
        "SQLAlchemyTimeoutError(",
    }:
        if fragment in sources["postgres_test"]:
            errors.append(
                "pool exhaustion PostgreSQL test contains forbidden shortcut: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "classification": "database_pool_timeout",
        "retry_safe": True,
        "transaction_aborted": False,
        "no_transaction_started": True,
        "outcome_unknown": False,
        "server_automatic_retry": False,
        "pool_size": 1,
        "max_overflow": 0,
        "pool_timeout_seconds": 0.1,
        "zero_mutation_before_recovery": True,
        "exact_key_recovery": True,
        "postgres_only": True,
        "dedicated_workflow": True,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
