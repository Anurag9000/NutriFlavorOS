#!/usr/bin/env python3
"""Validate the read-only preparation schedule support export boundary."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/support-export"
)
FILES = {
    "domain": "backend/domain/preparation_schedule_support_export.py",
    "service": "backend/services/preparation_schedule_support_export_service.py",
    "routes": "backend/api/preparation_operations_routes.py",
    "cli": "scripts/export_preparation_schedule_support_snapshot.py",
    "tests": "backend/tests/test_preparation_schedule_support_export.py",
    "postgres_tests": "backend/tests/test_preparation_schedule_support_export_postgres.py",
    "repair_workflow": ".github/workflows/preparation-repair.yml",
    "postgres_workflow": ".github/workflows/preparation-repair-postgres.yml",
    "openapi": "contracts/openapi_required.json",
    "docs": "docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing support export file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    operation = app.openapi().get("paths", {}).get(PATH, {}).get("get")
    if not isinstance(operation, dict):
        errors.append("generated OpenAPI lacks support export endpoint")
    else:
        if not operation.get("security"):
            errors.append("support export endpoint is not authenticated")
        schema = (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if schema.get("$ref") != "#/components/schemas/PreparationScheduleSupportExport":
            errors.append("support export response schema drifted")

    required = {
        "domain": {
            "class PreparationScheduleSupportExport",
            'Literal["preparation-schedule-support-export-v1"]',
            'Literal["repeatable_read", "serializable"]',
            "snapshot_read_only: Literal[True]",
            "related_repair_proposals",
            "repair_acceptances",
            "repair_proposal_events",
            "evidence_hash",
            "mutation_performed: Literal[False]",
            "actual_execution_verified: Literal[False]",
            "food_safety_verified: Literal[False]",
            "validate_cross_record_identity",
        },
        "service": {
            "def export_preparation_schedule_support_snapshot",
            'isolation_level="REPEATABLE READ"',
            'text("SET TRANSACTION READ ONLY")',
            'text("SELECT txid_current_snapshot()")',
            "get_schedule_derivation_evidence(",
            "get_task_execution_eligibility(",
            "get_task_execution_overview(",
            "get_repair_proposal(",
            "get_repair_proposal_acceptance(",
            "list_repair_proposal_events(",
            "def preparation_schedule_support_evidence_hash",
            '"mutation_performed": False',
            "transaction.rollback()",
        },
        "routes": {
            '"/schedules/{schedule_id}/support-export"',
            "response_model=PreparationScheduleSupportExport",
            "HouseholdRole.VIEWER",
            "return export_preparation_schedule_support_snapshot(",
        },
        "cli": {
            "def build_export_payload",
            "def write_atomic_json",
            "temporary.replace(path)",
            "--household-id",
            "--schedule-id",
            "--output",
            '"mutation_performed"',
        },
        "tests": {
            "test_original_schedule_export_is_hash_addressed_and_nonmutating",
            "test_source_and_replacement_exports_include_exact_repair_chain",
            "test_cli_helpers_render_and_atomically_replace_snapshot",
            "test_support_export_endpoint_requires_authentication",
            "test_viewer_authorized_support_export_returns_read_only_evidence",
            "test_support_export_preserves_cross_household_non_disclosure",
        },
        "postgres_tests": {
            "test_postgres_support_export_is_repeatable_read_during_acceptance",
            "snapshot_started",
            "continue_export",
            'historical.snapshot_isolation == "repeatable_read"',
            "value.status.value for value in historical.related_repair_proposals",
            '== ["proposed"]',
            '== ["accepted"]',
            "current.evidence_hash != historical.evidence_hash",
        },
        "repair_workflow": {
            "preparation_schedule_support_export.py",
            "preparation_schedule_support_export_service.py",
            "test_preparation_schedule_support_export.py",
            "validate_preparation_schedule_support_export.py",
        },
        "postgres_workflow": {
            "test_preparation_schedule_support_export_postgres.py",
            "validate_preparation_schedule_support_export.py",
        },
        "openapi": {
            '"contract_version": "2026-08-03.1"',
            '"api_version": "0.15.3"',
            '"/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/support-export"',
            '"PreparationScheduleSupportExport"',
        },
        "docs": {
            "Preparation Schedule Support Export",
            "REPEATABLE READ",
            "SET TRANSACTION READ ONLY",
            "Canonical evidence hash",
            "Concurrent acceptance proof",
            "viewer access",
            "mutation_performed=false",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(f"{FILES[label]} lacks support export fragment: {fragment}")

    forbidden_service = {
        "db.add(",
        "db.delete(",
        "db.commit(",
        "snapshot_db.add(",
        "snapshot_db.delete(",
        "snapshot_db.commit(",
        "create_persisted_schedule(",
        "transition_schedule(",
        "record_task_execution_event(",
        "accept_repair_proposal(",
        "invalidate_repair_proposal(",
        "reject_repair_proposal(",
    }
    for fragment in sorted(forbidden_service):
        if fragment in sources["service"]:
            errors.append(f"support export service contains mutation: {fragment}")

    return {
        "valid": not errors,
        "path": PATH,
        "required_role": "viewer",
        "postgres_isolation": "repeatable_read",
        "postgres_read_only": True,
        "canonical_hash": "sha256",
        "source_formatting_normalized": True,
        "mutation_performed": False,
        "actual_execution_verified": False,
        "food_safety_verified": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
