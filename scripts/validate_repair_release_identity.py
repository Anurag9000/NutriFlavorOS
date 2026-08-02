#!/usr/bin/env python3
"""Validate synchronized repair release versions and reviewed migration head."""

from __future__ import annotations

import json
from pathlib import Path

from backend.main import app
from backend.schema_revision import CURRENT_ALEMBIC_REVISION


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_API = "0.15.1"
EXPECTED_OPENAPI_CONTRACT = "2026-08-02.11"
EXPECTED_MIGRATION = "20260802_0018"
ELIGIBILITY_PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/task-execution-eligibility"
)
DERIVATION_PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/derivation"
)
DERIVATION_COVERAGE_PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedule-derivation-coverage"
)


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing release identity file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


def validate_identity() -> dict:
    errors: list[str] = []
    contract_path = ROOT / "contracts/openapi_required.json"
    if not contract_path.is_file():
        errors.append("missing OpenAPI release contract")
        contract = {}
    else:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))

    if app.version != EXPECTED_API:
        errors.append(f"API version {app.version!r} != {EXPECTED_API!r}")
    if contract.get("api_version") != EXPECTED_API:
        errors.append("OpenAPI contract API version drifted")
    if contract.get("contract_version") != EXPECTED_OPENAPI_CONTRACT:
        errors.append("OpenAPI contract version drifted")
    if CURRENT_ALEMBIC_REVISION != EXPECTED_MIGRATION:
        errors.append("reviewed migration head drifted")

    required_paths = {
        ELIGIBILITY_PATH,
        DERIVATION_PATH,
        DERIVATION_COVERAGE_PATH,
    }
    contract_paths = set(contract.get("paths", {}))
    for path in sorted(required_paths - contract_paths):
        errors.append(f"OpenAPI release contract lacks required path: {path}")

    required_schemas = {
        "PreparationTaskExecutionEligibilityView",
        "PreparationScheduleDerivationEvidenceView",
        "PreparationScheduleDerivationCoverageView",
    }
    contract_schemas = set(contract.get("schemas", {}))
    for schema in sorted(required_schemas - contract_schemas):
        errors.append(f"OpenAPI release contract lacks required schema: {schema}")

    required_fragments = {
        "README.md": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI_CONTRACT}`",
            "One accepted replacement per source schedule version",
            "source_schedule_has_accepted_replacement",
            "Task-execution eligibility",
            "Schedule derivation evidence",
        },
        "docs/IMPLEMENTATION_STATUS.md": {
            f"**Database migration head:** `{EXPECTED_MIGRATION}`",
            f"**API version:** `{EXPECTED_API}`",
            f"**OpenAPI release contract:** `{EXPECTED_OPENAPI_CONTRACT}`",
            "One accepted replacement per source schedule version",
            "source_schedule_has_accepted_replacement",
            "Task-execution eligibility",
            "Schedule derivation evidence",
        },
        "docs/ROADMAP.md": {
            f"**Current migration head:** `{EXPECTED_MIGRATION}`",
            f"**Current API:** `{EXPECTED_API}`",
            f"**Current OpenAPI contract:** `{EXPECTED_OPENAPI_CONTRACT}`",
            "one-replacement-per-source invariant is implemented",
            "task-execution eligibility is implemented",
            "schedule derivation evidence is implemented",
        },
    }
    for relative, fragments in required_fragments.items():
        source = _read(relative, errors)
        for fragment in sorted(fragments):
            if fragment not in source:
                errors.append(f"{relative} lacks release fragment: {fragment}")

    main_source = _read("backend/main.py", errors)
    for fragment in {
        "preparation_schedule_derivation_routes",
        "preparation_task_execution_eligibility_routes",
        "app.include_router(preparation_schedule_derivation_routes.router)",
        "app.include_router(preparation_task_execution_eligibility_routes.router)",
    }:
        if fragment not in main_source:
            errors.append(f"backend/main.py lacks mounted release fragment: {fragment}")

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": contract.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "required_paths": sorted(required_paths),
        "required_schemas": sorted(required_schemas),
        "errors": errors,
    }


def main() -> int:
    report = validate_identity()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
