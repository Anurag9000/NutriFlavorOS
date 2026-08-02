#!/usr/bin/env python3
"""Validate one accepted repaired replacement per source schedule version."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from sqlalchemy import UniqueConstraint

from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.schema_revision import CURRENT_ALEMBIC_REVISION


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "migration": (
        "backend/migrations/versions/"
        "20260802_0018_unique_repair_source_acceptance.py"
    ),
    "guard": (
        "backend/services/"
        "preparation_repair_source_acceptance_guard_service.py"
    ),
    "routes": "backend/api/preparation_repair_proposal_routes.py",
    "tests": "backend/tests/test_preparation_repair_source_acceptance_guard.py",
    "postgres": "backend/tests/test_preparation_repair_acceptance_postgres.py",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing source-acceptance file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    if CURRENT_ALEMBIC_REVISION != "20260802_0018":
        errors.append("runtime migration head must be 20260802_0018")

    table = DBPreparationRepairProposalAcceptance.__table__
    uniques = {
        value.name: tuple(column.name for column in value.columns)
        for value in table.constraints
        if isinstance(value, UniqueConstraint)
    }
    if uniques.get("uq_preparation_repair_acceptance_source_version") != (
        "source_schedule_id",
        "source_schedule_version",
    ):
        errors.append("acceptance source-version uniqueness drifted")

    required = {
        "migration": {
            'revision = "20260802_0018"',
            'down_revision = "20260802_0017"',
            "_assert_no_duplicate_source_acceptances",
            "HAVING COUNT(*) > 1",
            "Cannot add one-replacement-per-source constraint",
            "uq_preparation_repair_acceptance_source_version",
            'batch.create_unique_constraint(',
        },
        "guard": {
            "def accept_repair_proposal_with_source_guard",
            "with_for_update()",
            "repair_source_already_has_accepted_replacement",
            "source_schedule_id",
            "source_schedule_version",
            "accepted_proposal_id",
            "accepted_schedule_id",
            "return accept_repair_proposal(",
        },
        "routes": {
            "accept_repair_proposal_with_source_guard",
            "return accept_repair_proposal_with_source_guard(",
        },
        "tests": {
            "test_source_guard_preserves_exact_retry_for_same_proposal",
            "test_source_guard_rejects_second_proposal_for_same_source_version",
            "test_database_constraint_blocks_direct_service_bypass",
            "repair_source_already_has_accepted_replacement",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks required fragment: {fragment}")

    if "return accept_repair_proposal(\n" in sources["routes"]:
        errors.append("proposal acceptance route bypasses source-level guard")

    for forbidden in [
        "db.commit(",
        "created_schedule_id =",
        "proposal.status =",
    ]:
        if forbidden in sources["guard"]:
            errors.append(f"source acceptance guard contains mutation: {forbidden}")

    return {
        "valid": not errors,
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "constraint": "uq_preparation_repair_acceptance_source_version",
        "columns": ["source_schedule_id", "source_schedule_version"],
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
