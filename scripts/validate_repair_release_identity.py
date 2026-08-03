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
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    else:
        contract = {}
        errors.append("missing OpenAPI release contract")

    if app.version != EXPECTED_API:
        errors.append(f"API version {app.version!r} != {EXPECTED_API!r}")
    if contract.get("api_version") != EXPECTED_API:
        errors.append("OpenAPI contract API version drifted")
    if contract.get("contract_version") != EXPECTED_OPENAPI_CONTRACT:
        errors.append("OpenAPI contract version drifted")
    if CURRENT_ALEMBIC_REVISION != EXPECTED_MIGRATION:
        errors.append("reviewed migration head drifted")

    for path in sorted(PATHS - set(contract.get("paths", {}))):
        errors.append(f"OpenAPI release contract lacks required path: {path}")
    for schema in sorted(SCHEMAS - set(contract.get("schemas", {}))):
        errors.append(f"OpenAPI release contract lacks required schema: {schema}")

    documentation = {
        "README.md": {
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
            "database recovery observability",
            "No public metrics HTTP endpoint",
            "controlled sustained pool pressure",
            "24 checkout timeouts",
            "not representative production capacity",
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
            "post-commit connection-loss evidence",
            "checked-out pool connection invalidation evidence",
            "bounded exact serialization retry",
            "three consecutive `40001` aborts",
            "database recovery observability",
            "privacy-preserving process metrics",
            "cross-replica aggregation",
            "controlled sustained pool pressure",
            "24 checkout timeouts",
            "zero lifecycle mutation",
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
            "C10 — PostgreSQL lifecycle, migration, and recovery evidence",
            "C11 — Read-only support evidence export",
            "C12 — Database recovery observability foundation",
            "C14 — Controlled sustained PostgreSQL pool pressure",
            "post-commit connection-loss recovery",
            "checked-out pool connection recovery",
            "bounded exact serialization retry",
            "three consecutive `40001` aborts",
            "database recovery observability",
            "cross-replica aggregation",
            "automatic_retry_performed=false",
            "controlled sustained pool pressure",
            "representative production capacity",
        },
        "docs/PREPARATION_REPAIR_ACCEPTANCE.md": {
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
        "docs/PREPARATION_REPAIR_POOL_INVALIDATION.md": {
            "PostgreSQL Pool Invalidation Recovery",
            "pool_pre_ping=True",
            "connection_invalidated=true",
            "retry_safe=false",
        },
        "docs/PREPARATION_REPAIR_POOL_EXHAUSTION.md": {
            "PostgreSQL Pool Exhaustion Recovery",
            "database_pool_timeout",
            "no_transaction_started=true",
            "same acceptance and schedule identities",
        },
        "docs/PREPARATION_REPAIR_POOL_PRESSURE.md": {
            "Controlled Sustained PostgreSQL Pool Pressure",
            "three synchronized waves",
            "eight callers per wave",
            "24 checkout timeouts",
            "exactly zero lifecycle mutation",
            "same idempotency key",
            "checkedout() == 0",
            "not representative production capacity",
        },
        "docs/PREPARATION_REPAIR_SERIALIZATION_RETRY.md": {
            "Bounded Exact Serialization Retry",
            "SERIALIZABLE",
            "SQLSTATE `40001`",
            "DatabaseOutcomeUnknown",
            "automatic_retry_performed=false",
        },
        "docs/DATABASE_RECOVERY_OBSERVABILITY.md": {
            "Database Recovery Observability",
            "never receives or stores SQL text",
            "retry_success_after_retry_total",
            "outcome-unknown events: critical",
            "1,600 concurrent updates",
            "no unauthenticated HTTP metrics endpoint",
            "cross-replica aggregation",
        },
        "docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md": {
            "Preparation Schedule Support Export",
            "Canonical evidence hash",
            "REPEATABLE READ",
            "SET TRANSACTION READ ONLY",
            "Snapshot-internal authorization",
            "mutation_performed=false",
        },
        "docs/PREPARATION_OPERATIONS.md": {
            f"API: `{EXPECTED_API}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI_CONTRACT}`",
            "retry_safe=true",
            "retry_safe=false",
            "checked-out pool connection invalidation",
        },
    }
    for relative, fragments in documentation.items():
        _require(relative, fragments, errors, "release")

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
            "database_transaction_retry_required",
            "database_commit_outcome_unknown",
            "database_pool_timeout",
            "retry_safe = transaction_aborted and not outcome_unknown",
            '"no_transaction_started": True',
            '"automatic_retry_performed": False',
            "DATABASE_RECOVERY_METRICS.record_operational_error(",
        },
        errors,
        "database failure boundary",
    )
    _require(
        "backend/database_recovery_metrics.py",
        {
            "class DatabaseRecoveryMetricsSnapshot",
            "class DatabaseRecoveryMetrics",
            "class DatabaseRecoveryAlertPolicy",
            "DATABASE_RECOVERY_METRICS = DatabaseRecoveryMetrics()",
            "record_retry_succeeded_after_retry",
            "record_retry_exhausted",
            "record_utility_outcome_unknown",
            "MappingProxyType(dict(self._code_counts))",
            '"database_pool_timeout"',
            '"08xxx"',
            "RLock()",
        },
        errors,
        "database recovery metrics",
    )
    _require(
        "backend/exact_database_retry.py",
        {
            "class ExactDatabaseRetryPolicy",
            "class DatabaseOutcomeUnknown",
            "classify_database_error",
            "DATABASE_RECOVERY_METRICS.record_retry_observation(",
            "DATABASE_RECOVERY_METRICS.record_retry_succeeded_after_retry()",
            "DATABASE_RECOVERY_METRICS.record_retry_exhausted()",
            "DATABASE_RECOVERY_METRICS.record_utility_outcome_unknown()",
        },
        errors,
        "bounded retry utility",
    )
    _require(
        "backend/tests/test_database_recovery_metrics.py",
        {
            "test_metrics_snapshot_sanitizes_labels_and_is_immutable",
            "test_http_error_handler_records_only_sanitized_classification",
            "test_bounded_retry_metrics_track_convergence_exhaustion_and_ambiguity",
            "test_alert_evaluation_uses_explicit_thresholds",
            "test_metrics_registry_is_thread_safe_and_monotonic",
            "test_invalid_metric_combinations_fail_before_counter_mutation",
            "retry_observation_total == 1600",
        },
        errors,
        "observability regressions",
    )
    _require(
        "scripts/validate_database_recovery_observability.py",
        {
            '"scope": "process_local"',
            '"sensitive_identifiers_recorded": False',
            '"public_http_endpoint": False',
            '"cross_replica_aggregation": False',
            '"alert_evaluation": True',
        },
        errors,
        "observability contract",
    )

    _require(
        "backend/api/preparation_operations_routes.py",
        {
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
            "transaction.rollback()",
        },
        errors,
        "snapshot authorization",
    )
    _require(
        "backend/tests/test_preparation_repair_connection_loss_postgres.py",
        {
            "test_postgres_connection_loss_after_commit_recovers_by_exact_retry",
            'text("SELECT pg_terminate_backend(:pid)")',
            'classification["retry_safe"] is False',
        },
        errors,
        "post-commit recovery",
    )
    _require(
        "backend/tests/test_preparation_repair_pool_invalidation_postgres.py",
        {
            "test_postgres_invalidated_checked_out_connection_recovers_on_fresh_session",
            "observed_error.connection_invalidated is True",
            "recovery_backend_pid != dead_backend_pid",
        },
        errors,
        "pool recovery",
    )
    _require(
        "backend/tests/test_preparation_repair_serialization_retry_postgres.py",
        {
            "test_postgres_repeated_serialization_failures_retry_exact_request_once",
            'isolation_level="SERIALIZABLE"',
            "failed_attempts = 3",
            "max_attempts=4",
            '"40001"',
            '"acceptances": 1',
            '"replacement_schedules": 1',
        },
        errors,
        "serialization recovery",
    )
    _require(
        "backend/tests/test_preparation_repair_pool_exhaustion_postgres.py",
        {
            "test_postgres_pool_exhaustion_times_out_before_mutation_and_recovers",
            "pool_size=1",
            "max_overflow=0",
            "pool_timeout=0.1",
            '"acceptances": 0',
            '"acceptances": 1',
        },
        errors,
        "single pool exhaustion",
    )
    _require(
        "backend/tests/test_preparation_repair_pool_pressure_postgres.py",
        {
            "test_postgres_sustained_pool_pressure_times_out_cleanly_then_recovers",
            "POOL_SIZE = 2",
            "WORKERS_PER_WAVE = 8",
            "PRESSURE_WAVES = 3",
            "EXPECTED_TIMEOUTS = WORKERS_PER_WAVE * PRESSURE_WAVES",
            "ThreadPoolExecutor(max_workers=WORKERS_PER_WAVE)",
            "Barrier(WORKERS_PER_WAVE + 1)",
            "snapshot.retry_exhausted_total == EXPECTED_TIMEOUTS",
            "constrained_engine.pool.checkedout() == 0",
            "replayed.acceptance.id == accepted.acceptance.id",
        },
        errors,
        "sustained pool pressure",
    )
    _require(
        "scripts/validate_preparation_repair_pool_pressure_contract.py",
        {
            "_integer_expression",
            '"expected_checkout_timeouts": 24',
            '"derived_constant_evaluation": True',
            '"zero_mutation_before_recovery": True',
            '"representative_production_capacity": False',
        },
        errors,
        "sustained pool pressure contract",
    )

    _require(
        ".github/workflows/preparation-repair.yml",
        {
            "backend/database_recovery_metrics.py",
            "backend/tests/test_database_recovery_metrics.py",
            "validate_database_recovery_observability.py",
            "validate_preparation_repair_serialization_retry_contract.py",
            "validate_repair_release_identity.py",
        },
        errors,
        "SQLite repair workflow",
    )
    _require(
        ".github/workflows/preparation-repair-postgres.yml",
        {
            "backend/database_recovery_metrics.py",
            "backend/tests/test_database_recovery_metrics.py",
            "validate_database_recovery_observability.py",
            "test_preparation_repair_connection_loss_postgres.py",
            "test_preparation_repair_pool_invalidation_postgres.py",
            "test_preparation_repair_serialization_retry_postgres.py",
            "reports/preparation-repair-postgres.xml",
        },
        errors,
        "PostgreSQL evidence workflow",
    )
    _require(
        ".github/workflows/preparation-repair-pool-exhaustion.yml",
        {
            "test_database_pool_timeout_boundary.py",
            "test_preparation_repair_pool_exhaustion_postgres.py",
            "test_preparation_repair_pool_pressure_postgres.py",
            "validate_preparation_repair_pool_exhaustion_contract.py",
            "validate_preparation_repair_pool_pressure_contract.py",
            "reports/preparation-repair-pool-exhaustion.xml",
        },
        errors,
        "pool pressure evidence workflow",
    )

    main_source = _read("backend/main.py", errors)
    for forbidden in {
        "database-recovery-metrics",
        "snapshot_database_recovery_metrics",
        "DATABASE_RECOVERY_METRICS.snapshot",
    }:
        if forbidden in main_source:
            errors.append(f"backend/main.py exposes forbidden metrics surface: {forbidden}")

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
        "controlled_pool_exhaustion": True,
        "controlled_sustained_pool_pressure": True,
        "pressure_waves": 3,
        "pressure_workers_per_wave": 8,
        "pressure_timeout_count": 24,
        "pressure_zero_mutation": True,
        "pressure_pool_checked_out_after_recovery": 0,
        "representative_production_capacity": False,
        "database_recovery_observability": True,
        "metrics_scope": "process_local",
        "metrics_sensitive_identifiers_recorded": False,
        "metrics_public_http_endpoint": False,
        "server_automatic_retry": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_identity()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
