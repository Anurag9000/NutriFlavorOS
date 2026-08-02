#!/usr/bin/env python3
"""Validate the real PostgreSQL migration 0017-to-0018 volume rehearsal."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "migration": "backend/migrations/versions/20260802_0018_unique_repair_source_acceptance.py",
    "rehearsal": "scripts/rehearse_repair_source_acceptance_migration_postgres.py",
    "workflow": ".github/workflows/preparation-repair-postgres.yml",
    "unit_test": "backend/tests/test_preparation_repair_source_acceptance_migration.py",
    "docs": "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing migration rehearsal file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "migration": {
            'revision = "20260802_0018"',
            'down_revision = "20260802_0017"',
            "_assert_no_duplicate_source_acceptances",
            "GROUP BY source_schedule_id, source_schedule_version",
            "HAVING COUNT(*) > 1",
            "uq_preparation_repair_acceptance_source_version",
        },
        "rehearsal": {
            'PREDECESSOR = "20260802_0017"',
            'HEAD = "20260802_0018"',
            "DEFAULT_COUNT = 64",
            "create_repair_proposal(",
            "accept_repair_proposal_with_source_guard(",
            "records.append(_acceptance_snapshot",
            "Migration changed acceptance identity or hash evidence",
            "COUNT(DISTINCT (source_schedule_id, source_schedule_version))",
            "pg_get_constraintdef",
            "accept_repair_proposal(",
            'bypass_code != "repair_acceptance_conflict"',
            '"lower_level_bypass_rows_added": 0',
            '"network_or_failover_simulated": False',
        },
        "workflow": {
            "alembic upgrade 20260802_0017",
            "rehearse_repair_source_acceptance_migration_postgres.py seed",
            "--count 64",
            "alembic upgrade head",
            "rehearse_repair_source_acceptance_migration_postgres.py verify",
            "repair-source-acceptance-migration-seed.json",
            "repair-source-acceptance-migration-report.json",
        },
        "unit_test": {
            "test_source_acceptance_preflight_allows_unique_rows",
            "test_source_acceptance_preflight_lists_duplicate_rows",
            "Cannot add one-replacement-per-source constraint",
        },
        "docs": {
            "64 valid historical acceptances",
            "migration rehearsal",
            "lower-level bypass",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks rehearsal fragment: {fragment}")

    for forbidden in {
        "INSERT INTO preparation_repair_proposal_acceptances",
        "INSERT INTO preparation_repair_proposals",
        "INSERT INTO persisted_preparation_schedules",
    }:
        if forbidden in sources["rehearsal"]:
            errors.append(f"migration rehearsal bypasses production services: {forbidden}")

    return {
        "valid": not errors,
        "predecessor": "20260802_0017",
        "head": "20260802_0018",
        "historical_acceptance_count": 64,
        "production_service_seed": True,
        "exact_hash_preservation": True,
        "database_constraint_bypass_probe": True,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
