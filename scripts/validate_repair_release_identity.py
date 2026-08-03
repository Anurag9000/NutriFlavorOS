#!/usr/bin/env python3
"""Validate synchronized repair release versions and reviewed migration head."""

from __future__ import annotations

import json
from pathlib import Path

from backend.main import app
from backend.schema_revision import CURRENT_ALEMBIC_REVISION


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_API = "0.15.3"
EXPECTED_OPENAPI_CONTRACT = "2026-08-03.1"
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
SUPPORT_EXPORT_PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/support-export"
)
PROPOSAL_INVALIDATION_PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "repair-proposals/{proposal_id}/invalidate"
)


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing release identity file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


def _require_fragments(
    *,
    relative: str,
    source: str,
    fragments: set[str],
    errors: list[str],
    label: str,
) -> None:
    for fragment in sorted(fragments):
        if fragment not in source:
            errors.append(f"{relative} lacks {label} fragment: {fragment}")


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
        SUPPORT_EXPORT_PATH,
        PROPOSAL_INVALIDATION_PATH,
    }
    contract_paths = set(contract.get("paths", {}))
    for path in sorted(required_paths - contract_paths):
        errors.append(f"OpenAPI release contract lacks required path: {path}")

    required_schemas = {
        "PreparationTaskExecutionEligibilityView",
        "PreparationScheduleDerivationEvidenceView",
        "PreparationScheduleDerivationCoverageView",
        "PreparationScheduleSupportExport",
        "PreparationRepairProposalInvalidateRequest",
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
            "Owner-only proposal invalidation",
            "Lowest-layer task terminality",
            "Database transient failures and exact recovery",
            "Preparation schedule support export",
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            "64 valid accepted lifecycles",
        },
        "docs/IMPLEMENTATION_STATUS.md": {
            f"**Database migration head:** `{EXPECTED_MIGRATION}`",
            f"**API version:** `{EXPECTED_API}`",
            f"**OpenAPI release contract:** `{EXPECTED_OPENAPI_CONTRACT}`",
            "One accepted replacement per source schedule version",
            "source_schedule_has_accepted_replacement",
            "Task-execution eligibility",
            "Schedule derivation evidence",
            "Owner-only proposal invalidation",
            "Lowest-layer task terminality",
            "Database transient failures and exact recovery",
            "Preparation schedule support export",
            "explicit support-evidence generation/download",
            "statement-timeout evidence",
            "deadlock evidence",
            "64 valid accepted lifecycles",
        },
        "docs/ROADMAP.md": {
            f"**Current migration head:** `{EXPECTED_MIGRATION}`",
            f"**Current API:** `{EXPECTED_API}`",
            f"**Current OpenAPI contract:** `{EXPECTED_OPENAPI_CONTRACT}`",
            "one-replacement-per-source invariant is implemented",
            "task-execution eligibility is implemented",
            "schedule derivation evidence is implemented",
            "Owner-only proposal invalidation is implemented",
            "Lowest-layer task terminality",
            "C10 — PostgreSQL lifecycle, migration, and transient-failure evidence",
            "C11 — Read-only support evidence export",
            "automatic_retry_performed=false",
        },
        "docs/PREPARATION_REPAIR_EXECUTION_BOUNDARY.md": {
            "Lowest-layer schedule completion authority",
            "schedule_tasks_not_terminal",
            "Final-task concurrency boundary",
            "schedule_version_conflict",
        },
        "docs/PREPARATION_REPAIR_ACCEPTANCE.md": {
            "Migration rehearsal",
            "64 valid historical acceptances",
            "Statement timeout and deadlock recovery",
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            "same idempotency key",
            "no automatic retry",
        },
        "docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md": {
            "Preparation Schedule Support Export",
            "Canonical evidence hash",
            "REPEATABLE READ",
            "SET TRANSACTION READ ONLY",
            "Concurrent acceptance proof",
            "Viewer-authorized API",
            "Protected browser workspace",
            "mutation_performed=false",
        },
    }
    for relative, fragments in required_fragments.items():
        source = _read(relative, errors)
        _require_fragments(
            relative=relative,
            source=source,
            fragments=fragments,
            errors=errors,
            label="release",
        )

    main_source = _read("backend/main.py", errors)
    _require_fragments(
        relative="backend/main.py",
        source=main_source,
        fragments={
            'version="0.15.3"',
            "preparation_schedule_derivation_routes",
            "preparation_task_execution_eligibility_routes",
            "app.include_router(preparation_schedule_derivation_routes.router)",
            "app.include_router(preparation_task_execution_eligibility_routes.router)",
            "preparation_repair_proposal_routes",
            "database_error_handlers",
            "database_error_handlers.install_database_error_handlers(app)",
        },
        errors=errors,
        label="mounted release",
    )

    database_handler = _read("backend/api/database_error_handlers.py", errors)
    _require_fragments(
        relative="backend/api/database_error_handlers.py",
        source=database_handler,
        fragments={
            '"40001"',
            '"40P01"',
            '"57014"',
            '"55P03"',
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            '"automatic_retry_performed": False',
            'headers = {"Retry-After": "1"}',
        },
        errors=errors,
        label="database failure boundary",
    )

    operations_routes = _read(
        "backend/api/preparation_operations_routes.py",
        errors,
    )
    _require_fragments(
        relative="backend/api/preparation_operations_routes.py",
        source=operations_routes,
        fragments={
            '"/schedules/{schedule_id}/support-export"',
            "response_model=PreparationScheduleSupportExport",
            "HouseholdRole.VIEWER",
            "export_preparation_schedule_support_snapshot(",
        },
        errors=errors,
        label="support export route",
    )

    support_service = _read(
        "backend/services/preparation_schedule_support_export_service.py",
        errors,
    )
    _require_fragments(
        relative="backend/services/preparation_schedule_support_export_service.py",
        source=support_service,
        fragments={
            "def export_preparation_schedule_support_snapshot",
            'isolation_level="REPEATABLE READ"',
            'text("SET TRANSACTION READ ONLY")',
            'text("SELECT txid_current_snapshot()")',
            "def preparation_schedule_support_evidence_hash",
            '"mutation_performed": False',
        },
        errors=errors,
        label="support export service",
    )

    support_race = _read(
        "backend/tests/test_preparation_schedule_support_export_postgres.py",
        errors,
    )
    _require_fragments(
        relative="backend/tests/test_preparation_schedule_support_export_postgres.py",
        source=support_race,
        fragments={
            "test_postgres_support_export_is_repeatable_read_during_acceptance",
            'historical.snapshot_isolation == "repeatable_read"',
            '== ["proposed"]',
            '== ["accepted"]',
            "current.evidence_hash != historical.evidence_hash",
        },
        errors=errors,
        label="support export PostgreSQL evidence",
    )

    support_frontend_app = _read("frontend/src/App.tsx", errors)
    _require_fragments(
        relative="frontend/src/App.tsx",
        source=support_frontend_app,
        fragments={
            "PreparationScheduleSupportExport",
            'path="/preparation/operations/support-export"',
            "<ProtectedRoute>",
        },
        errors=errors,
        label="support export frontend route",
    )
    support_frontend_client = _read(
        "frontend/src/lib/preparationScheduleSupportExportApi.ts",
        errors,
    )
    _require_fragments(
        relative="frontend/src/lib/preparationScheduleSupportExportApi.ts",
        source=support_frontend_client,
        fragments={
            "export interface PreparationScheduleSupportExport",
            "/support-export",
            "preparationScheduleSupportExportApi = {",
            "get:",
            "supportExportFilename",
            "serializeSupportExport",
            "mutation_performed: false",
        },
        errors=errors,
        label="support export frontend client",
    )
    support_frontend_page = _read(
        "frontend/src/pages/PreparationScheduleSupportExport.tsx",
        errors,
    )
    _require_fragments(
        relative="frontend/src/pages/PreparationScheduleSupportExport.tsx",
        source=support_frontend_page,
        fragments={
            "Generate read-only snapshot",
            "Download JSON evidence",
            "Nothing is generated automatically",
            "Mutation performed: false",
            "Actual execution verified: false",
            "Food safety verified: false",
            "URL.revokeObjectURL(url)",
            '<p className="text-sm text-muted-foreground" aria-live="polite">',
        },
        errors=errors,
        label="support export frontend page",
    )
    for forbidden in {"<main", 'id="main-content"', "localStorage", "sessionStorage"}:
        if forbidden in support_frontend_page:
            errors.append(
                "support export frontend page contains forbidden release fragment: "
                f"{forbidden}"
            )

    support_frontend_sidebar = _read(
        "frontend/src/components/AppSidebar.tsx",
        errors,
    )
    _require_fragments(
        relative="frontend/src/components/AppSidebar.tsx",
        source=support_frontend_sidebar,
        fragments={
            'title: "Support Evidence Export"',
            'url: "/preparation/operations/support-export"',
        },
        errors=errors,
        label="support export navigation",
    )
    support_frontend_contract = _read(
        "scripts/validate_preparation_schedule_support_export_frontend.py",
        errors,
    )
    _require_fragments(
        relative="scripts/validate_preparation_schedule_support_export_frontend.py",
        source=support_frontend_contract,
        fragments={
            "explicit_generation_required",
            '"client_methods": ["get"]',
            '"browser_storage_used": False',
            '"main_landmark_owner": "AppLayout"',
        },
        errors=errors,
        label="support export frontend contract",
    )

    proposal_routes = _read(
        "backend/api/preparation_repair_proposal_routes.py",
        errors,
    )
    _require_fragments(
        relative="backend/api/preparation_repair_proposal_routes.py",
        source=proposal_routes,
        fragments={
            '"/{proposal_id}/invalidate"',
            "HouseholdRole.OWNER",
            "invalidate_repair_proposal(",
            "accept_repair_proposal_with_source_guard(",
        },
        errors=errors,
        label="proposal route",
    )

    completion_authority = _read(
        "backend/services/preparation_operations_service.py",
        errors,
    )
    _require_fragments(
        relative="backend/services/preparation_operations_service.py",
        source=completion_authority,
        fragments={
            "preparation_operations_service_impl as _impl",
            "def _assert_completion_authority",
            "assert_schedule_tasks_terminal(db, schedule=schedule)",
            "def transition_schedule",
        },
        errors=errors,
        label="completion authority",
    )

    completion_race = _read(
        "backend/tests/test_preparation_schedule_completion_postgres.py",
        errors,
    )
    _require_fragments(
        relative="backend/tests/test_preparation_schedule_completion_postgres.py",
        source=completion_race,
        fragments={
            "test_postgres_schedule_cannot_complete_ahead_of_final_task_event",
            '"schedule_tasks_not_terminal"',
            '"schedule_version_conflict"',
        },
        errors=errors,
        label="completion race",
    )

    transient_races = _read(
        "backend/tests/test_preparation_repair_transient_failures_postgres.py",
        errors,
    )
    _require_fragments(
        relative="backend/tests/test_preparation_repair_transient_failures_postgres.py",
        source=transient_races,
        fragments={
            "test_postgres_statement_timeout_rolls_back_then_exact_retry_succeeds",
            '"sqlstate": "57014"',
            "test_postgres_deadlock_victim_then_exact_retry_converges_once",
            'value.get("sqlstate") == "40P01"',
            'event_types == ["created", "accepted"]',
        },
        errors=errors,
        label="transient PostgreSQL evidence",
    )

    migration_rehearsal = _read(
        "scripts/rehearse_repair_source_acceptance_migration_postgres.py",
        errors,
    )
    _require_fragments(
        relative="scripts/rehearse_repair_source_acceptance_migration_postgres.py",
        source=migration_rehearsal,
        fragments={
            "DEFAULT_COUNT = 64",
            'PREDECESSOR = "20260802_0017"',
            'HEAD = "20260802_0018"',
            '"lower_level_bypass_rows_added": 0',
        },
        errors=errors,
        label="migration rehearsal",
    )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": contract.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "required_paths": sorted(required_paths),
        "required_schemas": sorted(required_schemas),
        "completion_authority": "transition_schedule",
        "database_transient_failure_boundary": True,
        "support_export": True,
        "support_export_frontend": True,
        "support_export_isolation": "repeatable_read",
        "support_export_mutation_performed": False,
        "automatic_retry_performed": False,
        "migration_rehearsal_count": 64,
        "errors": errors,
    }


def main() -> int:
    report = validate_identity()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
