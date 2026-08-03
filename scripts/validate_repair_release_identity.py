#!/usr/bin/env python3
"""Validate the synchronized preparation-repair release identity."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.main import app
from backend.schema_revision import CURRENT_ALEMBIC_REVISION


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_API = "0.15.4"
EXPECTED_OPENAPI_CONTRACT = "2026-08-03.2"
EXPECTED_MIGRATION = "20260802_0018"

PATHS = {
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/task-execution-eligibility",
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/derivation",
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedule-derivation-coverage",
    "/api/v1/households/{household_id}/preparation-operations/"
    "schedules/{schedule_id}/support-export",
    "/api/v1/households/{household_id}/preparation-operations/"
    "repair-proposals/{proposal_id}/invalidate",
}
SCHEMAS = {
    "PreparationTaskExecutionEligibilityView",
    "PreparationScheduleDerivationEvidenceView",
    "PreparationScheduleDerivationCoverageView",
    "PreparationScheduleSupportExport",
    "PreparationRepairProposalInvalidateRequest",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing release identity file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _require(
    relative: str,
    fragments: set[str],
    errors: list[str],
    label: str,
) -> str:
    source = _read(relative, errors)
    normalized = _normalized(source)
    for fragment in sorted(fragments):
        if fragment not in source and _normalized(fragment) not in normalized:
            errors.append(f"{relative} lacks {label} fragment: {fragment}")
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

    contract_paths = set(contract.get("paths", {}))
    for path in sorted(PATHS - contract_paths):
        errors.append(f"OpenAPI release contract lacks required path: {path}")
    contract_schemas = set(contract.get("schemas", {}))
    for schema in sorted(SCHEMAS - contract_schemas):
        errors.append(f"OpenAPI release contract lacks required schema: {schema}")

    _require(
        "README.md",
        {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI_CONTRACT}`",
            "One accepted replacement per source schedule version",
            "Owner-only proposal invalidation",
            "Schedule derivation evidence",
            "Lowest-layer task terminality",
            "Task-execution eligibility",
            "Preparation schedule support export",
            "Database transient failures and exact recovery",
            "database_commit_outcome_unknown",
            "retry_safe=false",
        },
        errors,
        "release",
    )
    _require(
        "docs/IMPLEMENTATION_STATUS.md",
        {
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
            "post-commit connection-loss evidence",
            "checked-out pool connection invalidation evidence",
            "bounded exact serialization retry",
            "three consecutive `40001` aborts",
            "retry_safe=false",
        },
        errors,
        "release",
    )
    _require(
        "docs/ROADMAP.md",
        {
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
            "bounded exact serialization retry",
            "three consecutive `40001` aborts",
            "retry_safe=false",
            "automatic_retry_performed=false",
        },
        errors,
        "release",
    )
    _require(
        "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
        {
            "creates exactly one new preparation schedule in `draft` state",
            "Owner approval remains a different endpoint and action",
            "The source schedule is never updated or deleted",
            "No step implies a later step",
            "Migration rehearsal",
            "64 valid historical acceptances",
            "Statement timeout and deadlock recovery",
            "Post-commit connection-loss recovery",
            "Checked-out pool connection recovery",
            "Repeated serialization recovery",
            "three consecutive SQLSTATE `40001`",
            "fourth exact-key attempt",
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            "same idempotency key",
            "no automatic retry",
        },
        errors,
        "acceptance release",
    )
    _require(
        "docs/PREPARATION_REPAIR_POOL_INVALIDATION.md",
        {
            "PostgreSQL Pool Invalidation Recovery",
            "pool_pre_ping=True",
            "connection_invalidated=true",
            "retry_safe=false",
            "same idempotency key",
        },
        errors,
        "pool recovery release",
    )
    _require(
        "docs/PREPARATION_REPAIR_SERIALIZATION_RETRY.md",
        {
            "Bounded Exact Serialization Retry",
            "SERIALIZABLE",
            "SQLSTATE `40001`",
            "same idempotency key",
            "DatabaseOutcomeUnknown",
            "automatic_retry_performed=false",
        },
        errors,
        "serialization retry release",
    )
    _require(
        "docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md",
        {
            "Preparation Schedule Support Export",
            "Canonical evidence hash",
            "REPEATABLE READ",
            "SET TRANSACTION READ ONLY",
            "Concurrent acceptance proof",
            "Snapshot-internal authorization",
            "Protected browser workspace",
            "mutation_performed=false",
        },
        errors,
        "support export release",
    )
    _require(
        "docs/PREPARATION_OPERATIONS.md",
        {
            f"API: `{EXPECTED_API}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI_CONTRACT}`",
            "retry_safe=true",
            "retry_safe=false",
            "checked-out pool connection invalidation",
        },
        errors,
        "preparation operations release",
    )

    _require(
        "backend/main.py",
        {
            'version="0.15.4"',
            "database_error_handlers.install_database_error_handlers(app)",
            "app.include_router(preparation_schedule_derivation_routes.router)",
            "app.include_router(preparation_task_execution_eligibility_routes.router)",
        },
        errors,
        "mounted release",
    )
    _require(
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
        },
        errors,
        "database failure boundary",
    )
    _require(
        "backend/tests/test_database_operational_error_handler.py",
        {
            '"retry_safe": True',
            'assert detail["retry_safe"] is False',
            "test_connection_exception_marks_commit_outcome_unknown",
            "test_invalidated_connection_without_sqlstate_is_ambiguous",
        },
        errors,
        "retry-safety regression",
    )

    _require(
        "backend/api/preparation_operations_routes.py",
        {
            '"/schedules/{schedule_id}/support-export"',
            "export_authorized_preparation_schedule_support_snapshot(",
            "authorized_user_id=current_user.id",
        },
        errors,
        "snapshot-authorized route",
    )
    _require(
        "backend/services/preparation_schedule_support_export_authorized_service.py",
        {
            "authorized_user_id: str",
            "require_household_access(",
            "HouseholdRole.VIEWER",
            'text("SET TRANSACTION READ ONLY")',
            'text("SELECT txid_current_snapshot()")',
            "transaction.rollback()",
        },
        errors,
        "snapshot authorization service",
    )
    _require(
        "backend/tests/test_preparation_schedule_support_export_authorization.py",
        {
            "test_authorized_support_snapshot_revalidates_owner_access",
            "test_authorized_support_snapshot_fails_closed_for_nonmember",
            "test_operator_snapshot_remains_explicitly_separate_from_http_authorization",
        },
        errors,
        "snapshot authorization tests",
    )

    _require(
        "backend/tests/test_preparation_repair_connection_loss_postgres.py",
        {
            "test_postgres_connection_loss_after_commit_recovers_by_exact_retry",
            'text("SELECT pg_terminate_backend(:pid)")',
            'classification["retry_safe"] is False',
            '"acceptances": 1',
            '"replacement_schedules": 1',
        },
        errors,
        "post-commit recovery evidence",
    )
    _require(
        "scripts/validate_preparation_repair_connection_loss_contract.py",
        {
            "pg_terminate_backend_after_commit_before_refresh",
            '"same_key_retry_required": True',
            '"retry_safe": False',
            '"ast_validated": True',
        },
        errors,
        "post-commit recovery contract",
    )
    _require(
        "backend/tests/test_preparation_repair_pool_invalidation_postgres.py",
        {
            "test_postgres_invalidated_checked_out_connection_recovers_on_fresh_session",
            'text("SELECT pg_terminate_backend(:pid)")',
            "observed_error.connection_invalidated is True",
            "recovery_backend_pid != dead_backend_pid",
            "exact_retry_session",
        },
        errors,
        "pool recovery evidence",
    )
    _require(
        "scripts/validate_preparation_repair_pool_invalidation_contract.py",
        {
            "terminate_checked_out_backend_before_mutation",
            '"pool_pre_ping": True',
            '"retry_safe": False',
            '"fresh_backend_required": True',
            '"ast_validated": True',
        },
        errors,
        "pool recovery contract",
    )

    _require(
        "backend/exact_database_retry.py",
        {
            "class ExactDatabaseRetryPolicy",
            "class DatabaseRetryObservation",
            "class DatabaseRetryExhausted",
            "class DatabaseOutcomeUnknown",
            "def execute_exact_idempotent_database_request",
            "for attempt in range(1, policy.max_attempts + 1)",
            "if outcome_unknown:",
            "raise DatabaseRetryExhausted(",
        },
        errors,
        "bounded retry utility",
    )
    _require(
        "backend/tests/test_exact_database_retry.py",
        {
            "test_retry_safe_aborts_preserve_key_and_emit_bounded_observations",
            "test_retry_safe_failure_exhausts_at_exact_bound",
            "test_outcome_unknown_is_observed_but_never_automatically_retried",
            "test_nonretryable_failure_is_re_raised_without_sleep",
            "test_policy_and_idempotency_key_validation",
        },
        errors,
        "bounded retry tests",
    )
    _require(
        "backend/tests/test_preparation_repair_serialization_retry_postgres.py",
        {
            "test_postgres_repeated_serialization_failures_retry_exact_request_once",
            'isolation_level="SERIALIZABLE"',
            "failed_attempts = 3",
            "max_attempts=4",
            '"40001"',
            "all(value.retry_safe is True for value in observations)",
            '"acceptances": 1',
            '"replacement_schedules": 1',
        },
        errors,
        "repeated serialization evidence",
    )
    _require(
        "scripts/validate_preparation_repair_serialization_retry_contract.py",
        {
            '"forced_abort_count": 3',
            '"maximum_attempts": 4',
            '"bounded_client_retry": True',
            '"outcome_unknown_automatic_retry": False',
            '"ast_validated": True',
        },
        errors,
        "serialization retry contract",
    )

    _require(
        ".github/workflows/preparation-repair.yml",
        {
            "backend/exact_database_retry.py",
            "backend/tests/test_exact_database_retry.py",
            "validate_preparation_repair_serialization_retry_contract.py",
            "preparation_schedule_support_export_authorized_service.py",
            "validate_repair_release_identity.py",
        },
        errors,
        "SQLite repair workflow",
    )
    _require(
        ".github/workflows/preparation-repair-postgres.yml",
        {
            "test_preparation_repair_connection_loss_postgres.py",
            "test_preparation_repair_pool_invalidation_postgres.py",
            "test_preparation_repair_serialization_retry_postgres.py",
            "validate_preparation_repair_connection_loss_contract.py",
            "validate_preparation_repair_pool_invalidation_contract.py",
            "validate_preparation_repair_serialization_retry_contract.py",
            "reports/preparation-repair-postgres.xml",
        },
        errors,
        "PostgreSQL evidence workflow",
    )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": contract.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "required_paths": sorted(PATHS),
        "required_schemas": sorted(SCHEMAS),
        "snapshot_internal_authorization": True,
        "post_commit_connection_loss_recovery": True,
        "checked_out_pool_recovery": True,
        "bounded_serialization_retry": True,
        "forced_serialization_abort_count": 3,
        "maximum_serialization_attempts": 4,
        "server_automatic_retry": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_identity()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
