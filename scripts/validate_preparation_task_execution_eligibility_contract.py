#!/usr/bin/env python3
"""Validate read-only preparation task-execution eligibility evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.domain.preparation_task_execution_eligibility import (
    PreparationTaskExecutionEligibilityView,
)
from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/task-execution-eligibility"
)
FILES = {
    "domain": "backend/domain/preparation_task_execution_eligibility.py",
    "service": "backend/services/preparation_task_execution_eligibility_service.py",
    "route": "backend/api/preparation_task_execution_eligibility_routes.py",
    "tests": "backend/tests/test_preparation_task_execution_eligibility.py",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing task-execution eligibility file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    expected_fields = {
        "schedule_id",
        "household_id",
        "schedule_version",
        "schedule_status",
        "eligible",
        "reason_code",
        "task_event_count",
        "accepted_proposal_id",
        "acceptance_id",
        "replacement_schedule_id",
        "replacement_schedule_status",
        "replacement_schedule_version",
    }
    fields = set(PreparationTaskExecutionEligibilityView.model_fields)
    if fields != expected_fields:
        errors.append(
            "task-execution eligibility fields drifted: "
            f"missing={sorted(expected_fields - fields)} "
            f"unexpected={sorted(fields - expected_fields)}"
        )

    operation = app.openapi().get("paths", {}).get(PATH, {}).get("get")
    if not isinstance(operation, dict):
        errors.append("generated OpenAPI lacks task-execution eligibility endpoint")
    else:
        if not operation.get("security"):
            errors.append("task-execution eligibility endpoint is not authenticated")
        schema = (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if schema.get("$ref") != (
            "#/components/schemas/PreparationTaskExecutionEligibilityView"
        ):
            errors.append("task-execution eligibility response schema drifted")

    required = {
        "domain": {
            "eligible execution requires approved schedule",
            "status-only block cannot expose replacement evidence",
            "replacement block requires complete replacement evidence",
            "SOURCE_HAS_ACCEPTED_REPLACEMENT",
        },
        "service": {
            "def get_task_execution_eligibility",
            "accepted_replacement_schedule_missing",
            "source_schedule_id == schedule.id",
            "task_event_count",
            "replacement_schedule_status",
            "schedule.status != \"approved\"",
        },
        "route": {
            '"/schedules/{schedule_id}/task-execution-eligibility"',
            "HouseholdRole.VIEWER",
            "get_task_execution_eligibility(",
        },
        "tests": {
            "test_approved_schedule_without_replacement_is_execution_eligible",
            "test_draft_schedule_is_not_execution_eligible",
            "test_source_schedule_reports_exact_accepted_replacement_block",
            "test_replacement_becomes_eligible_only_after_owner_approval",
            "test_task_execution_eligibility_endpoint_requires_authentication",
            "test_viewer_authorized_eligibility_endpoint_returns_reason",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks required fragment: {fragment}")

    for forbidden in [
        "db.commit(",
        "db.add(",
        "transition_schedule(",
        "record_task_execution_event(",
    ]:
        if forbidden in sources["service"]:
            errors.append(f"eligibility service contains mutation: {forbidden}")

    return {
        "valid": not errors,
        "path": PATH,
        "schema": "PreparationTaskExecutionEligibilityView",
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
