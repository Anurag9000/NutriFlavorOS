#!/usr/bin/env python3
"""Validate source-plan cancellation against repair acceptance and approval."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "plan_service": "backend/services/household_plan_lifecycle_service.py",
    "acceptance_service": "backend/services/preparation_repair_proposal_acceptance_service.py",
    "approval_guard": "backend/services/preparation_repair_approval_guard_service.py",
    "approval_service": "backend/services/preparation_schedule_approval_service.py",
    "source_guard": "backend/services/preparation_repair_source_acceptance_guard_service.py",
    "postgres_fixture": "backend/tests/postgres_preparation_fixture.py",
    "acceptance_test": "backend/tests/test_preparation_repair_plan_cancellation_postgres.py",
    "approval_test": "backend/tests/test_preparation_repair_plan_approval_postgres.py",
    "docs": "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing plan cancellation race file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "plan_service": {
            "def _lock_household",
            ".with_for_update()",
            "pg_advisory_xact_lock",
            "def _invalidate_dependent_schedules",
            "PreparationScheduleStatus.DRAFT.value",
            "PreparationScheduleStatus.APPROVED.value",
            "schedule.status = PreparationScheduleStatus.INVALIDATED.value",
            "invalidated_preparation_schedule_count",
            "def transition_household_plan",
            "db.commit()",
        },
        "acceptance_service": {
            "DBPersistedPreparationSchedule.id == proposal.source_schedule_id",
            ".with_for_update()",
            "assert_approved_source_plan(",
            "source_plan_id=source.source_plan_id",
            "source_plan_version=source.source_plan_version",
            "status=PreparationScheduleStatus.DRAFT.value",
            "db.commit()",
        },
        "approval_guard": {
            "def approve_schedule_with_repair_acceptance_guard",
            "_lock_household(db, household_id)",
            "return approve_schedule_authoritative(",
        },
        "approval_service": {
            "def approve_schedule_authoritative",
            "assert_approved_source_plan(",
            "source_plan_id=schedule.source_plan_id",
            "source_plan_version=schedule.source_plan_version",
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
            "test_postgres_source_plan_cancellation_dominates_repair_acceptance",
            "transition_household_plan(",
            "accept_repair_proposal_with_source_guard(",
            'assert final_plan.status == "cancelled"',
            'assert final_source.status == "invalidated"',
            'assert replacement.status == "invalidated"',
            "invalidated_schedule_ids == {source_id, replacement.id}",
            "live_linked_schedule_count == 0",
        },
        "approval_test": {
            "test_postgres_source_plan_cancellation_dominates_repaired_owner_approval",
            "approve_schedule_with_repair_acceptance_guard(",
            "transition_household_plan(",
            'assert final_plan.status == "cancelled"',
            'assert final_draft.status == "invalidated"',
            'draft_event_types == ["created", "approved", "invalidated"]',
            'draft_event_types == ["created", "invalidated"]',
            "live_linked_schedule_count == 0",
        },
        "docs": {
            "source plan cancellation",
            "invalidates",
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
        "final_plan_status": "cancelled",
        "live_linked_schedule_count": 0,
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
