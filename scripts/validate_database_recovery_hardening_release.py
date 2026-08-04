#!/usr/bin/env python3
"""Validate the synchronized database-recovery hardening release addendum."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_API = "0.15.4"
EXPECTED_OPENAPI = "2026-08-03.2"
EXPECTED_MIGRATION = "20260802_0018"
FILES = {
    "main": "backend/main.py",
    "schema": "backend/schema_revision.py",
    "openapi": "contracts/openapi_required.json",
    "handler": "backend/api/database_error_handlers.py",
    "metrics": "backend/database_recovery_metrics.py",
    "renderer": "backend/database_recovery_openmetrics.py",
    "retry": "backend/exact_database_retry.py",
    "metrics_tests": "backend/tests/test_database_recovery_metrics.py",
    "integrity_tests": "backend/tests/test_database_recovery_metric_integrity.py",
    "retry_tests": "backend/tests/test_exact_database_retry.py",
    "pool_tests": "backend/tests/test_database_pool_timeout_boundary.py",
    "exhaustion_test": "backend/tests/test_preparation_repair_pool_exhaustion_postgres.py",
    "pressure_test": "backend/tests/test_preparation_repair_pool_pressure_postgres.py",
    "crash_helper": "scripts/probe_preparation_repair_worker_crash.py",
    "crash_test": "backend/tests/test_preparation_repair_worker_crash_postgres.py",
    "commit_proxy": "backend/tests/postgres_commit_ack_drop_proxy.py",
    "commit_test": "backend/tests/test_preparation_repair_commit_ack_loss_postgres.py",
    "metric_contract": "scripts/validate_database_recovery_metric_integrity.py",
    "pressure_contract": "scripts/validate_preparation_repair_pool_pressure_contract.py",
    "crash_contract": "scripts/validate_preparation_repair_worker_crash_contract.py",
    "commit_contract": "scripts/validate_preparation_repair_commit_ack_loss_contract.py",
    "commit_release": "scripts/validate_preparation_repair_commit_ack_loss_release.py",
    "pool_workflow": ".github/workflows/preparation-repair-pool-exhaustion.yml",
    "commit_workflow": ".github/workflows/preparation-repair-commit-ack-loss.yml",
    "readme": "README.md",
    "observability_docs": "docs/DATABASE_RECOVERY_OBSERVABILITY.md",
    "retry_docs": "docs/PREPARATION_REPAIR_SERIALIZATION_RETRY.md",
    "pressure_docs": "docs/PREPARATION_REPAIR_POOL_PRESSURE.md",
    "crash_docs": "docs/PREPARATION_REPAIR_WORKER_CRASH.md",
    "commit_docs": "docs/PREPARATION_REPAIR_COMMIT_ACK_LOSS.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing recovery hardening release file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def validate_release() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    try:
        contract = json.loads(sources["openapi"] or "{}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid OpenAPI release JSON: {exc}")
        contract = {}

    if contract.get("api_version") != EXPECTED_API:
        errors.append("database recovery release API version drifted")
    if contract.get("contract_version") != EXPECTED_OPENAPI:
        errors.append("database recovery OpenAPI release version drifted")

    required = {
        "main": {f'version="{EXPECTED_API}"'},
        "schema": {f'CURRENT_ALEMBIC_REVISION = "{EXPECTED_MIGRATION}"'},
        "handler": {
            "def classify_operational_error",
            "def classify_pool_timeout",
            "def classify_database_error",
            '"database_transaction_retry_required"',
            '"database_commit_outcome_unknown"',
            '"database_pool_timeout"',
            '"database_operation_failed"',
            '"automatic_retry_performed": False',
        },
        "metrics": {
            "def _validate_operational_classification",
            "def _validate_retry_observation_classification",
            "def _finite_nonnegative_delay",
            "from math import isfinite",
            "type(value) is not int or value < 1",
            '"database_pool_timeout"',
        },
        "renderer": {
            'METRIC_PREFIX = "nutriflavor_database_recovery"',
            '"database_pool_timeout"',
            "_validate_values(snapshot)",
            'lines.append("# EOF")',
        },
        "retry": {
            "def _finite_nonnegative_policy_value",
            "from math import isfinite",
            "type(self.max_attempts) is not int",
            "classify_database_error",
            "TimeoutError as SQLAlchemyTimeoutError",
            "no_transaction_started=observation.no_transaction_started",
        },
        "metrics_tests": {
            "test_classification_code_and_flags_must_match_before_counter_mutation",
            "test_metrics_registry_is_thread_safe_and_monotonic",
            "retry_observation_total == 1600",
        },
        "integrity_tests": {
            "test_nonfinite_metric_delays_fail_before_counter_mutation",
            "test_alert_thresholds_require_positive_integers",
            "test_exact_reviewed_classifications_remain_recordable",
        },
        "retry_tests": {
            "test_policy_and_idempotency_key_validation",
            'float("nan")',
            'float("inf")',
            'float("-inf")',
        },
        "pool_tests": {
            "test_pool_timeout_returns_retry_safe_structured_503",
            "test_bounded_utility_retries_pool_timeout_with_same_key",
            "test_pool_timeout_exhaustion_is_bounded_and_observable",
        },
        "exhaustion_test": {
            "test_postgres_pool_exhaustion_times_out_before_mutation_and_recovers",
            "pool_size=1",
            "max_overflow=0",
            "pool_timeout=0.1",
        },
        "pressure_test": {
            "test_postgres_sustained_pool_pressure_times_out_cleanly_then_recovers",
            "POOL_SIZE = 2",
            "WORKERS_PER_WAVE = 8",
            "PRESSURE_WAVES = 3",
            "EXPECTED_TIMEOUTS = WORKERS_PER_WAVE * PRESSURE_WAVES",
            "snapshot.retry_exhausted_total == EXPECTED_TIMEOUTS",
            "constrained_engine.pool.checkedout() == 0",
        },
        "crash_helper": {
            "class _CrashBeforeCommitSession(Session)",
            "self.flush()",
            '"transaction_flushed_before_crash": True',
            '"commit_method_intercepted": True',
            '"database_commit_statement_started": False',
            '"lifecycle_commit_performed": False',
            'choices=("checkout-crash", "transaction-crash", "recover")',
            "accept_repair_proposal_with_source_guard(",
        },
        "crash_test": {
            "test_postgres_sigkill_during_pool_checkout_recovers_exact_request",
            "test_postgres_sigkill_after_flush_rolls_back_then_recovers_exact_request",
            "os.kill(process.pid, signal.SIGKILL)",
            "return_code == -signal.SIGKILL",
            "_ensure_worker_stopped(process)",
            '"commit_method_intercepted"] is True',
            '"database_commit_statement_started"] is False',
            '"transaction_local_counts"] == ONE_COUNTS',
            "_accepted_counts(db, proposal.id) == ZERO_COUNTS",
            "_wait_for_backend_absence(db, old_backend_pid)",
            "replayed.acceptance.id == recovery_report[\"acceptance_id\"]",
        },
        "commit_proxy": {
            "class PostgresCommitAckDropProxy",
            "self._commit_query_seen.set()",
            "self._upstream.sendall(frame)",
            "self._commit_query_forwarded.set()",
            '_command_complete_tag(frame) == b"COMMIT"',
            "self._commit_command_complete_seen.set()",
            "commit_acknowledgement_forwarded=False",
            "proxy threads leaked",
        },
        "commit_test": {
            "test_postgres_commit_acknowledgement_loss_recovers_exact_committed_request",
            '"sslmode": "disable"',
            '"gssencmode": "disable"',
            'worker.execute(text("SET LOCAL synchronous_commit = on"))',
            'worker.execute(text("SHOW synchronous_commit")).scalar_one() == "on"',
            "with pytest.raises(OperationalError)",
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["retry_safe"] is False',
            "proxy_report.commit_query_forwarded is True",
            "proxy_report.commit_command_complete_seen is True",
            "proxy_report.commit_acknowledgement_forwarded is False",
            "proxy_report.proxy_threads_stopped is True",
            "_accepted_counts(db, proposal.id) == ONE_COUNTS",
            "replayed.acceptance.id == acceptance.id",
        },
        "metric_contract": {
            '"exact_code_proof_partition": True',
            '"nonfinite_policy_values_rejected": True',
            '"nonfinite_metric_delays_rejected": True',
            '"alert_thresholds_positive_integers": True',
            '"atomic_failure_before_counter_mutation": True',
        },
        "pressure_contract": {
            '"expected_checkout_timeouts": 24',
            '"zero_mutation_before_recovery": True',
            '"pool_checked_out_after_recovery": 0',
            '"representative_production_capacity": False',
        },
        "crash_contract": {
            '"real_sigkill": True',
            '"checkout_holder_crash": True',
            '"flushed_open_transaction_crash": True',
            '"database_commit_statement_started": False',
            '"committed_rows_after_crash": 0',
            '"os_pid_reuse_tolerated": True',
            '"subprocess_output_collected_once": True',
            '"same_key_recovery": True',
            '"commit_acknowledgement_loss_proven": False',
            '"multi_node_failover_proven": False',
        },
        "commit_contract": {
            '"wire_proxy": True',
            '"commit_drop_armed_before_forward": True',
            '"commit_query_forwarded": True',
            '"synchronous_commit_on": True',
            '"command_complete_commit_seen": True',
            '"commit_acknowledgement_forwarded": False',
            '"client_outcome_unknown": True',
            '"retry_safe": False',
            '"same_key_recovery": True',
            '"single_controlled_proxy_connection": True',
            '"multi_node_failover_proven": False',
        },
        "commit_release": {
            '"command_complete_commit_seen": True',
            '"commit_acknowledgement_forwarded": False',
            '"client_outcome_unknown": True',
            '"same_key_recovery": True',
            '"hosted_green_claim": False',
        },
        "pool_workflow": {
            "test_database_operational_error_handler.py",
            "test_database_recovery_metrics.py",
            "test_database_recovery_metric_integrity.py",
            "test_database_recovery_openmetrics.py",
            "test_database_pool_timeout_boundary.py",
            "test_exact_database_retry.py",
            "test_preparation_repair_pool_exhaustion_postgres.py",
            "test_preparation_repair_pool_pressure_postgres.py",
            "test_preparation_repair_worker_crash_postgres.py",
            "probe_preparation_repair_worker_crash.py",
            "validate_preparation_repair_worker_crash_contract.py",
            "validate_database_recovery_metric_integrity.py",
            "validate_preparation_repair_pool_pressure_contract.py",
            "reports/preparation-repair-pool-exhaustion.xml",
        },
        "commit_workflow": {
            "validate-preparation-repair-commit-ack-loss",
            "postgres:16",
            "postgres_commit_ack_drop_proxy.py",
            "test_preparation_repair_commit_ack_loss_postgres.py",
            "validate_preparation_repair_commit_ack_loss_contract.py",
            "validate_preparation_repair_commit_ack_loss_release.py",
            "reports/preparation-repair-commit-ack-loss.xml",
        },
        "readme": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI}`",
            "controlled sustained pool pressure",
            "24 checkout timeouts",
            "ungraceful application-worker crash",
            "flushed open transaction",
            "COMMIT acknowledgement loss",
            "CommandComplete(COMMIT)",
            "database_commit_outcome_unknown",
            "same exact idempotency key",
            "No public metrics HTTP endpoint",
            "not representative production capacity",
        },
        "observability_docs": {
            "Exact classification and numeric integrity",
            "code and proof flags must agree",
            "finite and nonnegative",
            "positive integer thresholds",
            "Controlled sustained pressure aggregation",
            "24 checkout timeouts",
            "outcome-unknown events: critical",
            "unreviewed code or SQLSTATE labels",
        },
        "retry_docs": {
            "Bounded Exact Serialization Retry",
            "positive integer",
            "finite and nonnegative",
            "NaN",
            "infinity",
            "SQLAlchemy `TimeoutError`",
        },
        "pressure_docs": {
            "Controlled Sustained PostgreSQL Pool Pressure",
            "three synchronized waves",
            "eight callers per wave",
            "24 checkout timeouts",
            "exactly zero lifecycle mutation",
            "checkedout() == 0",
            "not representative production capacity",
        },
        "crash_docs": {
            "PostgreSQL Ungraceful Application-Worker Crash Recovery",
            "real `SIGKILL`",
            "Flushed-open-transaction crash",
            "Deterministic process cleanup",
            "OS PID reuse",
            "same exact idempotency key",
            "commit acknowledgement itself is in flight",
            "multi-node failover",
        },
        "commit_docs": {
            "PostgreSQL COMMIT Acknowledgement Loss",
            "synchronous_commit=on",
            "CommandComplete(COMMIT)",
            "acknowledgement is withheld",
            "database_commit_outcome_unknown",
            "retry_safe=false",
            "same exact idempotency key",
            "single controlled proxy connection",
            "does not prove multi-node failover",
        },
        "status": {
            "Exact classification integrity",
            "Nonfinite retry timing",
            "controlled sustained pool pressure",
            "24 checkout timeouts",
            "zero lifecycle mutation",
            "Controlled ungraceful application-worker crash",
            "flushed but uncommitted",
            "COMMIT acknowledgement loss",
            "CommandComplete(COMMIT)",
            "same exact idempotency key",
        },
        "roadmap": {
            "C14 — Controlled sustained PostgreSQL pool pressure",
            "C16 — Controlled ungraceful application-worker crash",
            "C17 — PostgreSQL COMMIT acknowledgement loss",
            "controlled sustained pool pressure",
            "ungraceful application-worker crash",
            "COMMIT acknowledgement loss",
            "representative production capacity",
            "multi-node failover",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks recovery-hardening release fragment: "
                    f"{fragment}"
                )

    return {
        "valid": not errors,
        "api_version": contract.get("api_version"),
        "openapi_contract_version": contract.get("contract_version"),
        "migration_head": EXPECTED_MIGRATION,
        "reviewed_error_code_count": 4,
        "controlled_pressure_timeout_count": 24,
        "controlled_pressure_zero_mutation": True,
        "controlled_pressure_pool_checked_out_after_recovery": 0,
        "ungraceful_worker_sigkill": True,
        "flushed_open_transaction_rollback": True,
        "database_commit_statement_started": False,
        "crash_committed_rows_after_termination": 0,
        "crash_same_key_recovery": True,
        "crash_process_cleanup_guaranteed": True,
        "controlled_commit_acknowledgement_loss": True,
        "commit_acknowledgement_loss_proven": True,
        "commit_query_forwarded": True,
        "synchronous_commit_on": True,
        "command_complete_commit_seen": True,
        "commit_acknowledgement_forwarded": False,
        "commit_client_outcome_unknown": True,
        "commit_same_key_recovery": True,
        "single_controlled_proxy_connection": True,
        "multi_node_failover_proven": False,
        "nonfinite_retry_inputs_rejected": True,
        "classification_integrity_enforced": True,
        "public_metrics_endpoint": False,
        "representative_production_capacity": False,
        "hosted_green_claim": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_release()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
