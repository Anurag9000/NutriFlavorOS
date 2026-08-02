#!/usr/bin/env python3
"""Validate household-level preparation schedule derivation coverage."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.domain.preparation_schedule_derivation_coverage import (
    PreparationScheduleDerivationCoverageView,
)
from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedule-derivation-coverage"
)
FILES = {
    "domain": "backend/domain/preparation_schedule_derivation_coverage.py",
    "service": "backend/services/preparation_schedule_derivation_coverage_service.py",
    "route": "backend/api/preparation_schedule_derivation_routes.py",
    "tests": "backend/tests/test_preparation_schedule_derivation_coverage.py",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing derivation coverage file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    expected_fields = {
        "household_id",
        "generated_at",
        "schedule_total",
        "original_schedule_count",
        "repair_schedule_count",
        "unknown_method_count",
        "complete_derivation_count",
        "incomplete_derivation_count",
        "accepted_proposal_count",
        "acceptance_record_count",
        "repaired_draft_count",
        "repaired_approved_count",
        "repaired_execution_history_count",
        "method_counts",
        "derivation_coverage_ratio",
        "repair_acceptance_link_coverage_ratio",
        "latest_acceptance_at",
        "warnings",
    }
    observed_fields = set(PreparationScheduleDerivationCoverageView.model_fields)
    if observed_fields != expected_fields:
        errors.append(
            "derivation coverage fields drifted: "
            f"missing={sorted(expected_fields - observed_fields)} "
            f"unexpected={sorted(observed_fields - expected_fields)}"
        )

    operation = app.openapi().get("paths", {}).get(PATH, {}).get("get")
    if not isinstance(operation, dict):
        errors.append("generated OpenAPI lacks derivation coverage endpoint")
    else:
        if not operation.get("security"):
            errors.append("derivation coverage endpoint is not authenticated")
        schema = (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if schema.get("$ref") != (
            "#/components/schemas/PreparationScheduleDerivationCoverageView"
        ):
            errors.append("derivation coverage response schema drifted")

    required_fragments = {
        "domain": {
            "derivation method counts must partition schedules",
            "derivation completeness counts must partition schedules",
            "repair lifecycle counts exceed repair schedule count",
        },
        "service": {
            "def get_schedule_derivation_coverage",
            "def _repair_evidence_complete",
            "original_schedule_count=original_count",
            "repair_schedule_count=repair_count",
            "unknown_method_count=unknown_count",
            "complete_derivation_count=complete_count",
            "incomplete_derivation_count=incomplete",
            "repair_acceptance_link_coverage_ratio",
            "has incomplete repair derivation evidence",
            "uses unknown derivation method",
        },
        "route": {
            '"/schedule-derivation-coverage"',
            "HouseholdRole.VIEWER",
            "get_schedule_derivation_coverage(",
        },
        "tests": {
            "test_empty_household_has_vacuous_complete_derivation_coverage",
            "test_original_schedule_counts_as_complete_without_repair_evidence",
            "test_accepted_repaired_draft_contributes_complete_acceptance_coverage",
            "test_tampered_acceptance_reduces_coverage_and_surfaces_warning",
            "test_derivation_coverage_endpoint_requires_authentication",
            "test_viewer_authorized_coverage_endpoint_returns_denominators",
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
            errors.append(f"derivation coverage service contains mutation: {forbidden}")

    return {
        "valid": not errors,
        "path": PATH,
        "schema": "PreparationScheduleDerivationCoverageView",
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
