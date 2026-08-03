#!/usr/bin/env python3
"""Validate controlled sustained PostgreSQL pool-pressure evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "test": "backend/tests/test_preparation_repair_pool_pressure_postgres.py",
    "single_exhaustion_test": (
        "backend/tests/test_preparation_repair_pool_exhaustion_postgres.py"
    ),
    "handler": "backend/api/database_error_handlers.py",
    "retry": "backend/exact_database_retry.py",
    "metrics": "backend/database_recovery_metrics.py",
    "workflow": ".github/workflows/preparation-repair-pool-exhaustion.yml",
    "docs": "docs/PREPARATION_REPAIR_POOL_PRESSURE.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing pool-pressure file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def _top_level_integer_constants(source: str) -> dict[str, int]:
    tree = ast.parse(source)
    values: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant) and type(node.value.value) is int:
            values[target.id] = node.value.value
    return values


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
        "test": {
            "test_postgres_sustained_pool_pressure_times_out_cleanly_then_recovers",
            "from concurrent.futures import ThreadPoolExecutor",
            "from threading import Barrier",
            "poolclass=QueuePool",
            "pool_size=POOL_SIZE",
            "max_overflow=0",
            "pool_timeout=POOL_TIMEOUT_SECONDS",
            "pool_pre_ping=True",
            "holders = [constrained_engine.connect() for _ in range(POOL_SIZE)]",
            'holder.execute(text("SELECT 1"))',
            "for wave in range(PRESSURE_WAVES)",
            "ThreadPoolExecutor(max_workers=WORKERS_PER_WAVE)",
            "Barrier(WORKERS_PER_WAVE + 1)",
            "DatabaseRetryExhausted",
            "max_attempts=1",
            '"database_pool_timeout"',
            '"no_transaction_started": True',
            '"outcome_unknown": False',
            '"acceptances": 0',
            '"replacement_schedules": 0',
            '"proposal_accepted_events": 0',
            '"replacement_created_events": 0',
            '"acceptances": 1',
            '"replacement_schedules": 1',
            "snapshot.retry_exhausted_total == EXPECTED_TIMEOUTS",
            "constrained_engine.pool.checkedout() == 0",
            "replayed.acceptance.id == accepted.acceptance.id",
            'health_connection.execute(text("SELECT 1"))',
            'db.get_bind().dialect.name == "postgresql"',
        },
        "single_exhaustion_test": {
            "test_postgres_pool_exhaustion_times_out_before_mutation_and_recovers",
            "pool_size=1",
            "max_overflow=0",
            "pool_timeout=0.1",
        },
        "handler": {
            "def classify_pool_timeout",
            '"code": "database_pool_timeout"',
            '"no_transaction_started": True',
            '"retry_safe": True',
            '"outcome_unknown": False',
        },
        "retry": {
            "classify_database_error",
            "TimeoutError as SQLAlchemyTimeoutError",
            "except (OperationalError, SQLAlchemyTimeoutError) as exc",
            "no_transaction_started=observation.no_transaction_started",
        },
        "metrics": {
            '"database_pool_timeout"',
            "pool_timeout_warning_threshold",
            "database_pool_checkout_timeout",
        },
        "workflow": {
            "test_preparation_repair_pool_pressure_postgres.py",
            "validate_preparation_repair_pool_pressure_contract.py",
            "reports/preparation-repair-pool-exhaustion.xml",
        },
        "docs": {
            "Controlled Sustained PostgreSQL Pool Pressure",
            "three synchronized waves",
            "eight callers per wave",
            "24 checkout timeouts",
            "exactly zero lifecycle mutation",
            "same idempotency key",
            "checkedout() == 0",
            "not representative production capacity",
        },
        "status": {
            "controlled sustained pool pressure",
            "24 checkout timeouts",
            "zero lifecycle mutation",
        },
        "roadmap": {
            "controlled sustained pool pressure",
            "representative production capacity",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks pool-pressure fragment: {fragment}"
                )

    constants = _top_level_integer_constants(sources["test"])
    expected_constants = {
        "POOL_SIZE": 2,
        "WORKERS_PER_WAVE": 8,
        "PRESSURE_WAVES": 3,
        "EXPECTED_TIMEOUTS": 24,
    }
    for name, expected in expected_constants.items():
        if constants.get(name) != expected:
            errors.append(
                f"pool-pressure constant {name} drifted: "
                f"{constants.get(name)!r} != {expected!r}"
            )

    expected_test = (
        "test_postgres_sustained_pool_pressure_times_out_cleanly_then_recovers"
    )
    if expected_test not in _test_names(sources["test"]):
        errors.append("controlled sustained PostgreSQL pool-pressure test is missing")

    forbidden = {
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "monkeypatch",
        "raise SQLAlchemyTimeoutError",
        "raise TimeoutError",
        "while True",
        "time.sleep(",
        "DBPreparationRepairProposalAcceptance(",
        "DBPersistedPreparationSchedule(",
        "representative_load_proven = True",
        "production_capacity_proven = True",
    }
    for fragment in sorted(forbidden):
        if fragment in sources["test"]:
            errors.append(
                "pool-pressure test contains forbidden shortcut or claim: "
                f"{fragment}"
            )

    lowered = sources["test"].lower()
    for fragment in ("sqlite://", "sqlite:///"):
        if fragment in lowered:
            errors.append("pool-pressure test contains a SQLite fallback")

    return {
        "valid": not errors,
        "database": "postgresql",
        "pool_size": 2,
        "max_overflow": 0,
        "pressure_waves": 3,
        "workers_per_wave": 8,
        "expected_checkout_timeouts": 24,
        "no_transaction_started": True,
        "zero_mutation_before_recovery": True,
        "same_key_recovery": True,
        "pool_checked_out_after_recovery": 0,
        "representative_production_capacity": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
