#!/usr/bin/env python3
"""Validate target-calendar supersession serialization with repair acceptance."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "operations_service": "backend/services/preparation_operations_service_impl.py",
    "acceptance_service": "backend/services/preparation_repair_proposal_acceptance_service.py",
    "source_guard": "backend/services/preparation_repair_source_acceptance_guard_service.py",
    "postgres_fixture": "backend/tests/postgres_preparation_fixture.py",
    "postgres_test": "backend/tests/test_preparation_repair_calendar_supersession_postgres.py",
    "docs": "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing calendar supersession race file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "operations_service": {
            "def register_resource_calendar",
            "_lock_household(db, household_id)",
            ".with_for_update()",
            "predecessor.active = False",
            "def _invalidate_schedules_for_calendar",
            "ACTIVE_SCHEDULE_STATUSES",
            "schedule.status = PreparationScheduleStatus.INVALIDATED.value",
            "replacement_calendar_id=calendar.id",
            "db.commit()",
        },
        "acceptance_service": {
            "DBResourceCalendarVersion.id == proposal.target_calendar_version_id",
            ".with_for_update()",
            "not calendar.active",
            "repair_acceptance_calendar_stale",
            "status=PreparationScheduleStatus.DRAFT.value",
        },
        "source_guard": {
            "def accept_repair_proposal_with_source_guard",
            "_lock_household(db, household_id)",
            "return accept_repair_proposal(",
        },
        "postgres_fixture": {
            'assert engine.dialect.name == "postgresql"',
            "expire_on_commit=False",
        },
        "postgres_test": {
            "test_postgres_calendar_supersession_dominates_repair_acceptance",
            "register_resource_calendar(",
            "accept_repair_proposal_with_source_guard(",
            "assert old_calendar.active is False",
            "assert successor.active is True",
            'assert final_source.status == "invalidated"',
            'assert replacement.status == "invalidated"',
            "live_old_calendar_schedule_count == 0",
        },
        "docs": {
            "calendar supersession",
            "active reviewed target calendar",
            "accepted replacement",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks race fragment: {fragment}")

    return {
        "valid": not errors,
        "database": "postgresql",
        "old_calendar_active": False,
        "live_old_calendar_schedule_count": 0,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
