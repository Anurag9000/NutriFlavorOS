#!/usr/bin/env python3
"""Validate that repair acceptance races are genuinely PostgreSQL-backed."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/preparation-repair-postgres.yml"
TEST = ROOT / "backend/tests/test_preparation_repair_acceptance_postgres.py"


def validate_contract() -> dict:
    errors: list[str] = []
    if not WORKFLOW.is_file():
        errors.append("missing PostgreSQL repair workflow")
        workflow = ""
    else:
        workflow = WORKFLOW.read_text(encoding="utf-8")
    if not TEST.is_file():
        errors.append("missing PostgreSQL repair race tests")
        tests = ""
    else:
        tests = TEST.read_text(encoding="utf-8")
        ast.parse(tests, filename=str(TEST.relative_to(ROOT)))

    workflow_fragments = {
        "image: postgres:16",
        "POSTGRES_DB: nutriflavor_test",
        "pg_isready -U postgres -d nutriflavor_test",
        "postgresql+psycopg://postgres:postgres@localhost:5432/nutriflavor_test",
        "alembic upgrade head",
        'assert engine.dialect.name == "postgresql"',
        'assert CURRENT_ALEMBIC_REVISION == "20260802_0017"',
        "verify_runtime_schema()",
        "test_preparation_repair_acceptance_postgres.py",
        "--junitxml=reports/preparation-repair-postgres.xml",
        "preparation-repair-postgres-races",
        "if-no-files-found: error",
    }
    for fragment in sorted(workflow_fragments):
        if fragment not in workflow:
            errors.append(f"PostgreSQL repair workflow lacks: {fragment}")

    test_fragments = {
        'db.get_bind().dialect.name == "postgresql"',
        "ThreadPoolExecutor",
        "Barrier",
        "test_postgres_exact_duplicate_acceptance_returns_one_draft",
        "test_postgres_competing_acceptance_keys_create_only_one_draft",
        "test_postgres_acceptance_racing_rejection_has_one_terminal_outcome",
        "_assert_single_acceptance_and_draft",
    }
    for fragment in sorted(test_fragments):
        if fragment not in tests:
            errors.append(f"PostgreSQL repair tests lack: {fragment}")

    for forbidden in [
        "sqlite://",
        "pytest.skip",
        "pytest.mark.skip",
        "xfail",
    ]:
        if forbidden in workflow or forbidden in tests:
            errors.append(f"PostgreSQL race gate contains forbidden fallback: {forbidden}")

    return {
        "valid": not errors,
        "workflow": str(WORKFLOW.relative_to(ROOT)),
        "test": str(TEST.relative_to(ROOT)),
        "database": "nutriflavor_test",
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
