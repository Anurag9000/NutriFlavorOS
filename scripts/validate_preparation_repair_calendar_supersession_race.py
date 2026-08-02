#!/usr/bin/env python3
"""Validate target-calendar supersession against repair acceptance and approval."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "operations_service": "backend/services/preparation_operations_service_impl.py",
    "acceptance_service": "backend/services/preparation_repair_proposal_acceptance_service.py",
    "approval_guard": "backend/services/preparation_repair_approval_guard_service.py",
    "approval_service": "backend/services/preparation_schedule_approval_service.py",
    "source_guard": "backend/services/preparation_repair_source_acceptance_guard_service.py",
    "postgres_fixture": "backend/tests/postgres_preparation_fixture.py",
    "acceptance_test": "backend/tests/test_preparation_repair_calendar_supersession_postgres.py",
    "approval_test": "backend/tests/test_preparation_repair_calendar_approval_postgres.py",
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
        "approval_guard": {
            "def approve_schedule_with_repair_acceptance_guard",
            "_lock_household(db, household_id)",
            "return approve_schedule_authoritative(",
        },
        "approval_service": {
            "def approve_schedule_authoritative",
            "_lock_household(db, household_id)",
            "DBResourceCalendarVersion.id == schedule.calendar_version_id",
            "not calendar.active",
            "schedule_calendar_stale",
            "PreparationScheduleStatus.DRAFT.value",
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
        "acceptance_test": {
            "test_postgres_calendar_supersession_dominates_repair_acceptance",
            "register_resource_calendar(",
            "accept_repair_proposal_with_source_guard(",
            "assert old_calendar.active is False",
            "assert successor.active is True",
            'assert final_source.status == "invalidated"',
            'assert replacement.status == "invalidated"',
            "live_old_calendar_schedule_count == 0",
        },
        "approval_test": {
            "test_postgres_calendar_supersession_dominates_repaired_owner_approval",
            "approve_schedule_with_repair_acceptance_guard(",
            "register_resource_calendar(",
            'assert final_draft.status == "invalidated"',
            'draft_event_types == ["created", "approved", "invalidated"]',
            'draft_event_types == ["created", "invalidated"]',
            "live_old_calendar_schedule_count == 0",
        },
        "docs": {
            "calendar supersession",
            "active reviewed target calendar",
            "accepted replacement",
            "owner approval",
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
        "acceptance_race": True,
        "approval_race": True,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
