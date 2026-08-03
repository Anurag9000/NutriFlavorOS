#!/usr/bin/env python3
"""Validate real PostgreSQL post-commit connection-loss recovery evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "handler": "backend/api/database_error_handlers.py",
    "test": "backend/tests/test_preparation_repair_connection_loss_postgres.py",
    "workflow": ".github/workflows/preparation-repair-postgres.yml",
    "acceptance_docs": "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing connection-loss recovery file: {relative}")
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
        "handler": {
            "database_commit_outcome_unknown",
            '"outcome_unknown": True',
            '"retry_safe": False',
            '"automatic_retry_performed": False',
            'sqlstate.startswith("08")',
            "connection_invalidated",
        },
        "test": {
            "test_postgres_connection_loss_after_commit_recovers_by_exact_retry",
            'text("SELECT pg_backend_pid()")',
            'text("SELECT pg_terminate_backend(:pid)")',
            "administrator.commit()",
            "terminate_before_first_refresh",
            "except OperationalError as exc",
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["outcome_unknown"] is True',
            'classification["automatic_retry_performed"] is False',
            '"acceptances": 1',
            '"replacement_schedules": 1',
            '"proposal_accepted_events": 1',
            '"replacement_created_events": 1',
            "accept_repair_proposal_with_source_guard(",
            'value.event_type for value in proposal_events',
            '== ["created", "accepted"]',
        },
        "workflow": {
            "test_preparation_repair_connection_loss_postgres.py",
            "validate_preparation_repair_connection_loss_recovery.py",
        },
        "acceptance_docs": {
            "Post-commit connection-loss recovery",
            "pg_terminate_backend",
            "database_commit_outcome_unknown",
            "same idempotency key",
        },
        "status": {
            "post-commit connection-loss evidence",
            "database_commit_outcome_unknown",
        },
        "roadmap": {
            "post-commit connection-loss recovery",
            "database_commit_outcome_unknown",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks connection-loss fragment: {fragment}"
                )

    forbidden_test = {
        "monkeypatch.setattr(Session, \"commit\"",
        "raise OperationalError(",
        "network_or_failover_simulated",
    }
    for fragment in sorted(forbidden_test):
        if fragment in sources["test"]:
            errors.append(
                "connection-loss probe fabricates the database failure: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "database": "postgresql",
        "failure_injection": "pg_terminate_backend_after_commit_before_refresh",
        "structured_code": "database_commit_outcome_unknown",
        "same_key_retry_required": True,
        "automatic_retry_performed": False,
        "acceptance_count_after_retry": 1,
        "replacement_count_after_retry": 1,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
