#!/usr/bin/env python3
"""Validate real PostgreSQL checked-out pool connection recovery evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "database": "backend/database.py",
    "handler": "backend/api/database_error_handlers.py",
    "test": "backend/tests/test_preparation_repair_pool_invalidation_postgres.py",
    "workflow": ".github/workflows/preparation-repair-postgres.yml",
    "docs": "docs/PREPARATION_REPAIR_POOL_INVALIDATION.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing pool-invalidation recovery file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "database": {
            '_engine_kwargs = {"pool_pre_ping": True}',
            "create_engine(DB_URL, **_engine_kwargs)",
        },
        "handler": {
            "database_commit_outcome_unknown",
            "connection_invalidated",
            "retry_safe = transaction_aborted and not outcome_unknown",
            '"retry_safe": retry_safe',
            '"automatic_retry_performed": False',
        },
        "test": {
            "test_postgres_invalidated_checked_out_connection_recovers_on_fresh_session",
            'text("SELECT pg_backend_pid()")',
            'text("SELECT pg_terminate_backend(:pid)")',
            "administrator.commit()",
            "observed_error.connection_invalidated is True",
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["retry_safe"] is False',
            '"acceptances": 0',
            '"replacement_schedules": 0',
            "recovery_backend_pid != dead_backend_pid",
            "exact_retry_session",
            '"acceptances": 1',
            '"replacement_schedules": 1',
            'assert [value.event_type for value in events] == ["created", "accepted"]',
        },
        "workflow": {
            "test_preparation_repair_pool_invalidation_postgres.py",
            "validate_preparation_repair_pool_invalidation_contract.py",
        },
        "docs": {
            "PostgreSQL Pool Invalidation Recovery",
            "pool_pre_ping=True",
            "connection_invalidated=true",
            "retry_safe=false",
            "fresh session and require its backend PID",
            "same idempotency key",
        },
        "status": {
            "checked-out pool connection invalidation evidence",
            "retry_safe=false",
        },
        "roadmap": {
            "checked-out pool connection recovery",
            "retry_safe=false",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks pool-invalidation fragment: {fragment}"
                )

    forbidden_test = {
        "raise OperationalError(",
        "monkeypatch",
        "engine.dispose()",
        "network_or_failover_simulated",
    }
    for fragment in sorted(forbidden_test):
        if fragment in sources["test"]:
            errors.append(f"pool recovery probe fabricates failure: {fragment}")

    tree = ast.parse(sources["test"])
    real_termination = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
        and any(
            isinstance(argument, ast.Call)
            and isinstance(argument.func, ast.Name)
            and argument.func.id == "text"
            and argument.args
            and isinstance(argument.args[0], ast.Constant)
            and "pg_terminate_backend" in str(argument.args[0].value)
            for argument in node.args
        )
        for node in ast.walk(tree)
    )
    if not real_termination:
        errors.append("pool recovery test AST lacks real pg_terminate_backend execution")

    return {
        "valid": not errors,
        "database": "postgresql",
        "pool_pre_ping": True,
        "failure_injection": "terminate_checked_out_backend_before_mutation",
        "connection_invalidated": True,
        "structured_code": "database_commit_outcome_unknown",
        "retryable": True,
        "retry_safe": False,
        "automatic_retry_performed": False,
        "fresh_backend_required": True,
        "exact_same_key_retry_required": True,
        "ast_validated": True,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
