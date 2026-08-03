#!/usr/bin/env python3
"""Validate the synchronized preparation-repair release identity."""

from __future__ import annotations

import json
from pathlib import Path

from backend.main import app
from backend.schema_revision import CURRENT_ALEMBIC_REVISION


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_API = "0.15.4"
EXPECTED_OPENAPI_CONTRACT = "2026-08-03.2"
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


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _require_fragments(
    *,
    relative: str,
    source: str,
    fragments: set[str],
    errors: list[str],
    label: str,
) -> None:
    normalized_source = _normalized(source)
    for fragment in sorted(fragments):
        if fragment not in source and _normalized(fragment) not in normalized_source:
            errors.append(f"{relative} lacks {label} fragment: {fragment}")


def _require_file(
    relative: str,
    fragments: set[str],
    errors: list[str],
    label: str,
) -> str:
    source = _read(relative, errors)
    _require_fragments(
        relative=relative,
        source=source,
        fragments=fragments,
        errors=errors,
        label=label,
    )
    return source


def validate_identity() -> dict:
    errors: list[str] = []
    contract_path = ROOT / "contracts/openapi_required.json"
    if not contract_path.is_file():
        errors.append("missing OpenAPI release contract")
        contract: dict[str, object] = {}
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

    documentation = {
        "README.md": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI_CONTRACT}`",
            "One accepted replacement per source schedule version",
            "64 valid accepted lifecycles",
            "Owner-only proposal invalidation",
            "Schedule derivation evidence",
            "Lowest-layer task terminality",
            "Task-execution eligibility",
            "source_schedule_has_accepted_replacement",
            "Preparation schedule support export",
            "Database transient failures and exact recovery",
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            "retry_safe=false",
            "checked-out pool connection invalidation evidence",
        },
        "docs/IMPLEMENTATION_STATUS.md": {
            f"**Database migration head:** `{EXPECTED_MIGRATION}`",
            f"**API version:** `{EXPECTED_API}`",
            f"**OpenAPI release contract:** `{EXPECTED_OPENAPI_CONTRACT}`",
            "One accepted replacement per source schedule version",
            "64 valid accepted lifecycles",
            "Owner-only proposal invalidation",
            "Schedule derivation evidence",
            "Lowest-layer task terminality",
            "Task-execution eligibility",
            "source_schedule_has_accepted_replacement",
            "Preparation schedule support export",
            "explicit support-evidence generation/download",
            "Database transient failures and exact recovery",
            "statement-timeout evidence",
            "deadlock evidence",
            "post-commit connection-loss evidence",
            "checked-out pool connection invalidation evidence",
            "retry_safe=false",
        },
        "docs/ROADMAP.md": {
            f"**Current migration head:** `{EXPECTED_MIGRATION}`",
            f"**Current API:** `{EXPECTED_API}`",
            f"**Current OpenAPI contract:** `{EXPECTED_OPENAPI_CONTRACT}`",
            "one-replacement-per-source invariant is implemented",
            "Schedule derivation evidence is implemented",
            "Task-execution eligibility is implemented",
            "Owner-only proposal invalidation is implemented",
            "Lowest-layer task terminality",
            "C10 — PostgreSQL lifecycle, migration, and transient-failure evidence",
            "C11 — Read-only support evidence export",
            "post-commit connection-loss recovery",
            "checked-out pool connection recovery",
            "retry_safe=false",
            "automatic_retry_performed=false",
        },
        "docs/PREPARATION_REPAIR_ACCEPTANCE.md": {
            "Migration rehearsal",
            "64 valid historical acceptances",
            "Statement timeout and deadlock recovery",
            "Post-commit connection-loss recovery",
            "pg_terminate_backend",
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            "same idempotency key",
            "no automatic retry",
        },
        "docs/PREPARATION_REPAIR_POOL_INVALIDATION.md": {
            "PostgreSQL Pool Invalidation Recovery",
            "pool_pre_ping=True",
            "connection_invalidated=true",
            "retry_safe=false",
            "same idempotency key",
        },
        "docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md": {
            "Preparation Schedule Support Export",
            "Canonical evidence hash",
            "REPEATABLE READ",
            "SET TRANSACTION READ ONLY",
            "Concurrent acceptance proof",
            "Snapshot-internal authorization",
            "Viewer-authorized API",
            "Protected browser workspace",
            "mutation_performed=false",
        },
        "docs/PREPARATION_OPERATIONS.md": {
            f"API: `{EXPECTED_API}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI_CONTRACT}`",
            "retry_safe=true",
            "retry_safe=false",
            "checked-out pool connection invalidation",
        },
        "docs/PREPARATION_REPAIR_EXECUTION_BOUNDARY.md": {
            "Lowest-layer schedule completion authority",
            "schedule_tasks_not_terminal",
            "Final-task concurrency boundary",
            "schedule_version_conflict",
        },
    }
    for relative, fragments in documentation.items():
        _require_file(relative, fragments, errors, "release")

    _require_file(
        "backend/main.py",
        {
            'version="0.15.4"',
            "preparation_schedule_derivation_routes",
            "preparation_task_execution_eligibility_routes",
            "app.include_router(preparation_schedule_derivation_routes.router)",
            "app.include_router(preparation_task_execution_eligibility_routes.router)",
            "preparation_repair_proposal_routes",
            "database_error_handlers.install_database_error_handlers(app)",
        },
        errors,
        "mounted release",
    )

    _require_file(
        "backend/api/database_error_handlers.py",
        {
            '"40001"',
            '"40P01"',
            '"57014"',
            '"55P03"',
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            "retry_safe = transaction_aborted and not outcome_unknown",
            '"retry_safe": retry_safe',
            '"automatic_retry_performed": False',
            'headers = {"Retry-After": "1"}',
        },
        errors,
        "database failure boundary",
    )

    _require_file(
        "backend/tests/test_database_operational_error_handler.py",
        {
            '"retry_safe": True',
            'assert detail["retry_safe"] is False',
            "test_connection_exception_marks_commit_outcome_unknown",
            "test_invalidated_connection_without_sqlstate_is_ambiguous",
        },
        errors,
        "database retry-safety test",
    )

    _require_file(
        "backend/api/preparation_operations_routes.py",
        {
            '"/schedules/{schedule_id}/support-export"',
            "response_model=PreparationScheduleSupportExport",
            "HouseholdRole.VIEWER",
            "export_authorized_preparation_schedule_support_snapshot(",
            "authorized_user_id=current_user.id",
        },
        errors,
        "support export route",
    )

    _require_file(
        "backend/services/preparation_schedule_support_export_service.py",
        {
            "def export_preparation_schedule_support_snapshot",
            'isolation_level="REPEATABLE READ"',
            'text("SET TRANSACTION READ ONLY")',
            'text("SELECT txid_current_snapshot()")',
            "def preparation_schedule_support_evidence_hash",
            '"mutation_performed": False',
        },
        errors,
        "operator support export",
    )

    _require_file(
        "backend/services/preparation_schedule_support_export_authorized_service.py",
        {
            "def export_authorized_preparation_schedule_support_snapshot",
            "authorized_user_id: str",
            "require_household_access(",
            "HouseholdRole.VIEWER",
            'text("SET TRANSACTION READ ONLY")',
            'text("SELECT txid_current_snapshot()")',
            "_build_snapshot(",
            "transaction.rollback()",
        },
        errors,
        "snapshot-authorized support export",
    )

    _require_file(
        "backend/tests/test_preparation_schedule_support_export_authorization.py",
        {
            "test_authorized_support_snapshot_revalidates_owner_access",
            "test_authorized_support_snapshot_fails_closed_for_nonmember",
            "test_operator_snapshot_remains_explicitly_separate_from_http_authorization",
            "authorized_user_id=OWNER_ID",
            "authorized_user_id=outsider_id",
            "assert exc.value.status_code == 404",
        },
        errors,
        "support authorization regression",
    )

    _require_file(
        "backend/tests/test_preparation_schedule_support_export_postgres.py",
        {
            "test_postgres_support_export_is_repeatable_read_during_acceptance",
            'historical.snapshot_isolation == "repeatable_read"',
            '== ["proposed"]',
            '== ["accepted"]',
            "current.evidence_hash != historical.evidence_hash",
        },
        errors,
        "support export PostgreSQL evidence",
    )

    support_page = _require_file(
        "frontend/src/pages/PreparationScheduleSupportExport.tsx",
        {
            "Generate read-only snapshot",
            "Download JSON evidence",
            "Nothing is generated automatically",
            "Mutation performed: false",
            "Actual execution verified: false",
            "Food safety verified: false",
            "URL.revokeObjectURL(url)",
            "resultRef.current?.focus()",
            'aria-live="polite"',
        },
        errors,
        "support export frontend",
    )
    for forbidden in {"<main", 'id="main-content"', "localStorage", "sessionStorage"}:
        if forbidden in support_page:
            errors.append(
                "support export frontend contains forbidden release fragment: "
                f"{forbidden}"
            )

    _require_file(
        "frontend/src/App.tsx",
        {
            "PreparationScheduleSupportExport",
            'path="/preparation/operations/support-export"',
            "<ProtectedRoute>",
        },
        errors,
        "support export route",
    )
    _require_file(
        "frontend/src/components/AppSidebar.tsx",
        {
            'title: "Support Evidence Export"',
            'url: "/preparation/operations/support-export"',
        },
        errors,
        "support export navigation",
    )
    _require_file(
        "scripts/validate_preparation_schedule_support_export_frontend.py",
        {
            "explicit_generation_required",
            '"client_methods": ["get"]',
            '"browser_storage_used": False',
            '"main_landmark_owner": "AppLayout"',
        },
        errors,
        "support export frontend contract",
    )

    _require_file(
        "backend/tests/test_preparation_repair_connection_loss_postgres.py",
        {
            "test_postgres_connection_loss_after_commit_recovers_by_exact_retry",
            'text("SELECT pg_backend_pid()")',
            'text("SELECT pg_terminate_backend(:pid)")',
            "terminate_before_first_refresh",
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["retry_safe"] is False',
            '"acceptances": 1',
            '"replacement_schedules": 1',
        },
        errors,
        "post-commit connection-loss evidence",
    )
    _require_file(
        "scripts/validate_preparation_repair_connection_loss_contract.py",
        {
            "pg_terminate_backend_after_commit_before_refresh",
            "database_commit_outcome_unknown",
            '"same_key_retry_required": True',
            '"retry_safe": False',
            '"automatic_retry_performed": False',
            '"ast_validated": True',
        },
        errors,
        "connection-loss contract",
    )

    _require_file(
        "backend/tests/test_preparation_repair_pool_invalidation_postgres.py",
        {
            "test_postgres_invalidated_checked_out_connection_recovers_on_fresh_session",
            'text("SELECT pg_backend_pid()")',
            'text("SELECT pg_terminate_backend(:pid)")',
            "observed_error.connection_invalidated is True",
            'classification["retry_safe"] is False',
            "recovery_backend_pid != dead_backend_pid",
            "exact_retry_session",
            '"acceptances": 0',
            '"acceptances": 1',
        },
        errors,
        "pool invalidation evidence",
    )
    _require_file(
        "scripts/validate_preparation_repair_pool_invalidation_contract.py",
        {
            "terminate_checked_out_backend_before_mutation",
            "database_commit_outcome_unknown",
            '"pool_pre_ping": True',
            '"retry_safe": False',
            '"fresh_backend_required": True',
            '"ast_validated": True',
        },
        errors,
        "pool invalidation contract",
    )

    _require_file(
        ".github/workflows/preparation-repair-postgres.yml",
        {
            "preparation_schedule_support_export_authorized_service.py",
            "test_preparation_repair_connection_loss_postgres.py",
            "validate_preparation_repair_connection_loss_contract.py",
            "test_preparation_repair_pool_invalidation_postgres.py",
            "validate_preparation_repair_pool_invalidation_contract.py",
            "reports/preparation-repair-postgres.xml",
        },
        errors,
        "PostgreSQL workflow",
    )
    _require_file(
        ".github/workflows/preparation-repair.yml",
        {
            "preparation_schedule_support_export_authorized_service.py",
            "test_preparation_schedule_support_export_authorization.py",
            "validate_preparation_repair_connection_loss_contract.py",
            "validate_preparation_repair_pool_invalidation_contract.py",
            "test_database_operational_error_handler.py",
        },
        errors,
        "focused repair workflow",
    )

    _require_file(
        "backend/api/preparation_repair_proposal_routes.py",
        {
            '"/{proposal_id}/invalidate"',
            "HouseholdRole.OWNER",
            "invalidate_repair_proposal(",
            "accept_repair_proposal_with_source_guard(",
        },
        errors,
        "proposal route",
    )
    _require_file(
        "backend/services/preparation_operations_service.py",
        {
            "preparation_operations_service_impl as _impl",
            "def _assert_completion_authority",
            "assert_schedule_tasks_terminal(db, schedule=schedule)",
            "def transition_schedule",
        },
        errors,
        "completion authority",
    )
    _require_file(
        "backend/tests/test_preparation_schedule_completion_postgres.py",
        {
            "test_postgres_schedule_cannot_complete_ahead_of_final_task_event",
            '"schedule_tasks_not_terminal"',
            '"schedule_version_conflict"',
        },
        errors,
        "completion race",
    )
    _require_file(
        "backend/tests/test_preparation_repair_transient_failures_postgres.py",
        {
            "test_postgres_statement_timeout_rolls_back_then_exact_retry_succeeds",
            '"sqlstate": "57014"',
            "test_postgres_deadlock_victim_then_exact_retry_converges_once",
            'value.get("sqlstate") == "40P01"',
            'event_types == ["created", "accepted"]',
        },
        errors,
        "transient PostgreSQL evidence",
    )
    _require_file(
        "scripts/rehearse_repair_source_acceptance_migration_postgres.py",
        {
            "DEFAULT_COUNT = 64",
            'PREDECESSOR = "20260802_0017"',
            'HEAD = "20260802_0018"',
            '"lower_level_bypass_rows_added": 0',
        },
        errors,
        "migration rehearsal",
    )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": contract.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "required_paths": sorted(required_paths),
        "required_schemas": sorted(required_schemas),
        "source_formatting_normalized": True,
        "completion_authority": "transition_schedule",
        "database_transient_failure_boundary": True,
        "transaction_abort_retry_safe": True,
        "connection_outcome_retry_safe": False,
        "post_commit_connection_loss_recovery": True,
        "checked_out_pool_connection_recovery": True,
        "support_export": True,
        "support_export_frontend": True,
        "support_export_snapshot_authorization": True,
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
