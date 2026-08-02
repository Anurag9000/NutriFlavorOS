#!/usr/bin/env python3
"""Validate authorized, fail-closed preparation schedule derivation evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.domain.preparation_schedule_derivation import (
    PreparationScheduleDerivationEvidenceView,
)
from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/derivation"
)
FILES = {
    "domain": "backend/domain/preparation_schedule_derivation.py",
    "service": "backend/services/preparation_schedule_derivation_service.py",
    "route": "backend/api/preparation_schedule_derivation_routes.py",
    "tests": "backend/tests/test_preparation_schedule_derivation.py",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing derivation evidence file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required_fields = {
        "schedule_id",
        "household_id",
        "schedule_version",
        "schedule_status",
        "schedule_hash",
        "derivation_method",
        "evidence_complete",
        "source_repair_proposal_id",
        "source_repair_proposal_version",
        "source_repair_acceptance_id",
        "source_schedule_id",
        "source_schedule_version",
        "source_schedule_hash",
        "source_schedule_request_hash",
        "target_calendar_content_hash",
        "repair_request_hash",
        "repair_result_hash",
        "revised_request_hash",
        "repaired_response_hash",
        "accepted_by_user_id",
        "accepted_at",
        "acceptance_reason",
        "warnings",
        "created_at",
        "updated_at",
    }
    fields = set(PreparationScheduleDerivationEvidenceView.model_fields)
    if fields != required_fields:
        errors.append(
            "derivation evidence fields drifted: "
            f"missing={sorted(required_fields - fields)} "
            f"unexpected={sorted(fields - required_fields)}"
        )

    operation = app.openapi().get("paths", {}).get(PATH, {}).get("get")
    if not isinstance(operation, dict):
        errors.append("generated OpenAPI lacks schedule derivation endpoint")
    else:
        if not operation.get("security"):
            errors.append("schedule derivation endpoint is not authenticated")
        schema = (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if schema.get("$ref") != (
            "#/components/schemas/PreparationScheduleDerivationEvidenceView"
        ):
            errors.append("schedule derivation response schema drifted")

    required_fragments = {
        "domain": {
            "validate_method_partition",
            "original schedule cannot expose repair derivation evidence",
            "repair-derived schedule requires complete acceptance evidence",
        },
        "service": {
            "def get_schedule_derivation_evidence",
            "schedule_derivation_evidence_mismatch",
            "original_schedule_has_repair_evidence",
            "repair_schedule_derivation_evidence_missing",
            "acknowledged_task_ids",
            "acceptance_repair_result_hash",
        },
        "route": {
            "HouseholdRole.VIEWER",
            '"/schedules/{schedule_id}/derivation"',
            "get_schedule_derivation_evidence(",
        },
        "tests": {
            "test_original_schedule_reports_original_method_and_no_repair_evidence",
            "test_accepted_repaired_draft_reports_complete_cross_record_evidence",
            "test_derivation_read_fails_closed_after_acceptance_tamper",
            "test_derivation_service_preserves_household_non_disclosure",
            "test_derivation_endpoint_requires_authentication",
            "test_viewer_authorized_derivation_endpoint_returns_exact_evidence",
        },
    }
    for label, fragments in required_fragments.items():
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
            errors.append(f"derivation read service contains mutation: {forbidden}")

    return {
        "valid": not errors,
        "path": PATH,
        "schema": "PreparationScheduleDerivationEvidenceView",
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
