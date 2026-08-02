#!/usr/bin/env python3
"""Validate that accepted repair sources cannot begin task execution."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "guard": (
        "backend/services/"
        "preparation_task_execution_replacement_guard_service.py"
    ),
    "routes": "backend/api/preparation_operations_routes.py",
    "tests": "backend/tests/test_preparation_task_execution_replacement_guard.py",
    "postgres": "backend/tests/test_preparation_repair_source_acceptance_postgres.py",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing replacement execution file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "guard": {
            "def record_task_execution_event_with_replacement_guard",
            "_lock_household(db, household_id)",
            "with_for_update()",
            "source_schedule_has_accepted_replacement",
            "accepted_proposal_id",
            "acceptance_id",
            "replacement_schedule_id",
            "return _record_task_execution_event(",
        },
        "routes": {
            "preparation_task_execution_replacement_guard_service",
            "record_task_execution_event_with_replacement_guard as record_task_execution_event",
        },
        "tests": {
            "test_source_schedule_rejects_task_execution_after_repair_acceptance",
            "test_approved_replacement_schedule_can_record_task_execution",
            "source_schedule_has_accepted_replacement",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks required fragment: {fragment}")

    if (
        "record_task_execution_event as record_task_execution_event"
        in sources["routes"]
    ):
        errors.append("task execution route bypasses accepted-replacement guard")

    for forbidden in [
        "db.commit(",
        "schedule.status =",
        "proposal.status =",
        "replacement.created_schedule_id =",
    ]:
        if forbidden in sources["guard"]:
            errors.append(f"replacement execution guard contains mutation: {forbidden}")

    return {
        "valid": not errors,
        "boundary": "accepted_repair_source_cannot_execute",
        "error_code": "source_schedule_has_accepted_replacement",
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
