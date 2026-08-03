#!/usr/bin/env python3
"""Validate privacy-preserving database recovery observability."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "metrics": "backend/database_recovery_metrics.py",
    "renderer": "backend/database_recovery_openmetrics.py",
    "handler": "backend/api/database_error_handlers.py",
    "retry": "backend/exact_database_retry.py",
    "tests": "backend/tests/test_database_recovery_metrics.py",
    "renderer_tests": "backend/tests/test_database_recovery_openmetrics.py",
    "pool_tests": "backend/tests/test_database_pool_timeout_boundary.py",
    "pressure_test": "backend/tests/test_preparation_repair_pool_pressure_postgres.py",
    "repair_workflow": ".github/workflows/preparation-repair.yml",
    "postgres_workflow": ".github/workflows/preparation-repair-postgres.yml",
    "pool_workflow": ".github/workflows/preparation-repair-pool-exhaustion.yml",
    "docs": "docs/DATABASE_RECOVERY_OBSERVABILITY.md",
    "pressure_docs": "docs/PREPARATION_REPAIR_POOL_PRESSURE.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
    "main": "backend/main.py",
}

EXPECTED_SNAPSHOT_FIELDS = {
    "generated_at",
    "operational_error_total",
    "transaction_abort_total",
    "outcome_unknown_total",
    "nonretryable_error_total",
    "retry_observation_total",
    "retry_scheduled_total",
    "retry_success_after_retry_total",
    "retry_exhausted_total",
    "utility_outcome_unknown_total",
    "invalidated_connection_total",
    "retry_delay_seconds_total",
    "retry_delay_seconds_max",
    "code_counts",
    "sqlstate_counts",
}
EXPECTED_CODES = {
    "database_transaction_retry_required",
    "database_commit_outcome_unknown",
    "database_pool_timeout",
    "database_operation_failed",
}
EXPECTED_SQLSTATE_BUCKETS = {
    "40001",
    "40P01",
    "57014",
    "55P03",
    "08xxx",
    "unknown",
}
FORBIDDEN_SENSITIVE_NAMES = {
    "sql_text",
    "statement",
    "parameters",
    "idempotency_key",
    "household_id",
    "user_id",
    "proposal_id",
    "schedule_id",
    "exception_message",
    "request_payload",
    "payload",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing observability file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def _class_annotations(source: str, class_name: str) -> set[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                child.target.id
                for child in node.body
                if isinstance(child, ast.AnnAssign)
                and isinstance(child.target, ast.Name)
            }
    return set()


def _method_argument_names(source: str, class_name: str) -> dict[str, set[str]]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            result: dict[str, set[str]] = {}
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[child.name] = {
                        argument.arg
                        for argument in (
                            child.args.posonlyargs
                            + child.args.args
                            + child.args.kwonlyargs
                        )
                        if argument.arg != "self"
                    }
            return result
    return {}


def _test_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "metrics": {
            "class DatabaseRecoveryMetricsSnapshot",
            "class DatabaseRecoveryMetrics",
            "class DatabaseRecoveryAlertPolicy",
            "class DatabaseRecoveryAlert",
            "DATABASE_RECOVERY_METRICS = DatabaseRecoveryMetrics()",
            "def snapshot_database_recovery_metrics",
            "def evaluate_database_recovery_alerts",
            "MappingProxyType(dict(self._code_counts))",
            "MappingProxyType(dict(self._sqlstate_counts))",
            '"database_pool_timeout"',
            '"08xxx"',
            '"unknown"',
            "pool_timeout_warning_threshold",
            "database_pool_checkout_timeout",
            "no_transaction_started: bool = False",
            "record_retry_succeeded_after_retry",
            "record_retry_exhausted",
            "record_utility_outcome_unknown",
            "RLock()",
        },
        "renderer": {
            'METRIC_PREFIX = "nutriflavor_database_recovery"',
            "def render_database_recovery_openmetrics",
            "_validate_bounded_labels(snapshot)",
            "_validate_values(snapshot)",
            '"database_transaction_retry_required"',
            '"database_commit_outcome_unknown"',
            '"database_pool_timeout"',
            '"database_operation_failed"',
            '"40001"',
            '"40P01"',
            '"57014"',
            '"55P03"',
            '"08xxx"',
            '"unknown"',
            "isfinite(numeric)",
            'lines.append("# EOF")',
        },
        "handler": {
            "from backend.database_recovery_metrics import DATABASE_RECOVERY_METRICS",
            "def classify_pool_timeout",
            "def classify_database_error",
            "database_pool_timeout_handler",
            '"code": "database_pool_timeout"',
            '"no_transaction_started": True',
            "DATABASE_RECOVERY_METRICS.record_operational_error(",
            '"automatic_retry_performed": False',
        },
        "retry": {
            "from backend.database_recovery_metrics import DATABASE_RECOVERY_METRICS",
            "TimeoutError as SQLAlchemyTimeoutError",
            "classify_database_error",
            "except (OperationalError, SQLAlchemyTimeoutError) as exc",
            "DATABASE_RECOVERY_METRICS.record_retry_observation(",
            "no_transaction_started=observation.no_transaction_started",
            "DATABASE_RECOVERY_METRICS.record_retry_succeeded_after_retry()",
            "DATABASE_RECOVERY_METRICS.record_retry_exhausted()",
            "DATABASE_RECOVERY_METRICS.record_utility_outcome_unknown()",
        },
        "tests": {
            "test_metrics_snapshot_sanitizes_labels_and_is_immutable",
            "test_http_error_handler_records_only_sanitized_classification",
            "test_bounded_retry_metrics_track_convergence_exhaustion_and_ambiguity",
            "test_alert_evaluation_uses_explicit_thresholds",
            "test_metrics_registry_is_thread_safe_and_monotonic",
            "test_invalid_metric_combinations_fail_before_counter_mutation",
            "retry_observation_total == 1600",
            'assert "metrics-success-key" not in rendered',
            'assert "sensitive SQL statement" not in rendered',
        },
        "renderer_tests": {
            "test_openmetrics_render_is_deterministic_and_complete",
            "test_openmetrics_render_contains_no_domain_or_request_identifiers",
            "test_openmetrics_rejects_unbounded_error_code_label",
            "test_openmetrics_rejects_unbounded_sqlstate_label",
            "test_openmetrics_rejects_negative_or_nonfinite_values",
            "test_openmetrics_empty_label_maps_remain_valid",
            'assert rendered.count("# EOF") == 1',
            'assert "idempotency"',
        },
        "pool_tests": {
            "test_pool_timeout_returns_retry_safe_structured_503",
            "test_bounded_utility_retries_pool_timeout_with_same_key",
            "test_pool_timeout_exhaustion_is_bounded_and_observable",
            "test_pool_timeout_alert_and_openmetrics_are_bounded",
            '"database_pool_timeout"',
            '"no_transaction_started": True',
        },
        "pressure_test": {
            "test_postgres_sustained_pool_pressure_times_out_cleanly_then_recovers",
            "EXPECTED_TIMEOUTS = WORKERS_PER_WAVE * PRESSURE_WAVES",
            "snapshot.code_counts == {",
            '"database_pool_timeout": EXPECTED_TIMEOUTS',
            "snapshot.retry_observation_total == EXPECTED_TIMEOUTS",
            "snapshot.retry_exhausted_total == EXPECTED_TIMEOUTS",
            "snapshot.retry_scheduled_total == 0",
            "snapshot.outcome_unknown_total == 0",
            "snapshot.invalidated_connection_total == 0",
        },
        "repair_workflow": {
            "backend/database_recovery_metrics.py",
            "backend/database_recovery_openmetrics.py",
            "backend/tests/test_database_recovery_metrics.py",
            "backend/tests/test_database_recovery_openmetrics.py",
            "validate_database_recovery_observability.py",
        },
        "postgres_workflow": {
            "backend/database_recovery_metrics.py",
            "backend/database_recovery_openmetrics.py",
            "backend/tests/test_database_recovery_metrics.py",
            "backend/tests/test_database_recovery_openmetrics.py",
            "validate_database_recovery_observability.py",
        },
        "pool_workflow": {
            "backend/database_recovery_metrics.py",
            "backend/database_recovery_openmetrics.py",
            "test_database_pool_timeout_boundary.py",
            "test_preparation_repair_pool_pressure_postgres.py",
            "validate_database_recovery_observability.py",
            "validate_preparation_repair_pool_pressure_contract.py",
        },
        "docs": {
            "Database Recovery Observability",
            "never receives or stores SQL text",
            "retry_success_after_retry_total",
            "database_pool_timeout",
            "Sanitized OpenMetrics adapter",
            "nutriflavor_database_recovery",
            "four reviewed error codes",
            "Controlled sustained pressure aggregation",
            "24 checkout timeouts",
            "1,600 concurrent updates",
            "no unauthenticated HTTP metrics endpoint",
        },
        "pressure_docs": {
            "Controlled Sustained PostgreSQL Pool Pressure",
            "24 checkout timeouts",
            "exactly zero lifecycle mutation",
            "not representative production capacity",
        },
        "status": {
            "database recovery observability",
            "privacy-preserving process metrics",
            "controlled sustained pool pressure",
            "24 checkout timeouts",
        },
        "roadmap": {
            "database recovery observability",
            "cross-replica aggregation",
            "controlled sustained pool pressure",
            "representative production capacity",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks observability fragment: {fragment}"
                )

    snapshot_fields = _class_annotations(
        sources["metrics"],
        "DatabaseRecoveryMetricsSnapshot",
    )
    if snapshot_fields != EXPECTED_SNAPSHOT_FIELDS:
        errors.append(
            "database recovery snapshot fields drifted: "
            f"{sorted(snapshot_fields)}"
        )
    for field in sorted(snapshot_fields & FORBIDDEN_SENSITIVE_NAMES):
        errors.append(f"sensitive metric snapshot field is forbidden: {field}")

    method_arguments = _method_argument_names(
        sources["metrics"],
        "DatabaseRecoveryMetrics",
    )
    for method, arguments in sorted(method_arguments.items()):
        for argument in sorted(arguments & FORBIDDEN_SENSITIVE_NAMES):
            errors.append(
                f"metrics method {method} accepts sensitive argument: {argument}"
            )

    expected_tests = {
        "test_metrics_snapshot_sanitizes_labels_and_is_immutable",
        "test_http_error_handler_records_only_sanitized_classification",
        "test_bounded_retry_metrics_track_convergence_exhaustion_and_ambiguity",
        "test_alert_evaluation_uses_explicit_thresholds",
        "test_metrics_registry_is_thread_safe_and_monotonic",
        "test_invalid_metric_combinations_fail_before_counter_mutation",
    }
    for name in sorted(expected_tests - _test_names(sources["tests"])):
        errors.append(f"database recovery observability test is missing: {name}")

    expected_renderer_tests = {
        "test_openmetrics_render_is_deterministic_and_complete",
        "test_openmetrics_render_contains_no_domain_or_request_identifiers",
        "test_openmetrics_rejects_unbounded_error_code_label",
        "test_openmetrics_rejects_unbounded_sqlstate_label",
        "test_openmetrics_rejects_negative_or_nonfinite_values",
        "test_openmetrics_empty_label_maps_remain_valid",
    }
    for name in sorted(
        expected_renderer_tests - _test_names(sources["renderer_tests"])
    ):
        errors.append(f"database recovery OpenMetrics test is missing: {name}")

    expected_pool_tests = {
        "test_pool_timeout_returns_retry_safe_structured_503",
        "test_bounded_utility_retries_pool_timeout_with_same_key",
        "test_pool_timeout_exhaustion_is_bounded_and_observable",
        "test_pool_timeout_alert_and_openmetrics_are_bounded",
    }
    for name in sorted(expected_pool_tests - _test_names(sources["pool_tests"])):
        errors.append(f"database pool-timeout test is missing: {name}")

    pressure_name = (
        "test_postgres_sustained_pool_pressure_times_out_cleanly_then_recovers"
    )
    if pressure_name not in _test_names(sources["pressure_test"]):
        errors.append("sustained PostgreSQL pool-pressure metrics test is missing")

    forbidden_main = {
        "database-recovery-metrics",
        "DATABASE_RECOVERY_METRICS.snapshot",
        "snapshot_database_recovery_metrics",
        "render_database_recovery_openmetrics",
    }
    for fragment in sorted(forbidden_main):
        if fragment in sources["main"]:
            errors.append(
                "application exposes an unreviewed public metrics surface: "
                f"{fragment}"
            )

    forbidden_metrics = {
        "FastAPI",
        "APIRouter",
        "@router.",
        "idempotency_key:",
        "household_id:",
        "user_id:",
        "proposal_id:",
        "schedule_id:",
        "sql_text:",
        "parameters:",
        "exception_message:",
    }
    for label in ("metrics", "renderer"):
        for fragment in sorted(forbidden_metrics):
            if fragment in sources[label]:
                errors.append(
                    f"{FILES[label]} contains forbidden observability surface: "
                    f"{fragment}"
                )

    for code in sorted(EXPECTED_CODES):
        if code not in sources["metrics"] or code not in sources["renderer"]:
            errors.append(f"reviewed observability code is not shared: {code}")
    for bucket in sorted(EXPECTED_SQLSTATE_BUCKETS):
        if bucket not in sources["renderer"]:
            errors.append(f"reviewed SQLSTATE bucket is missing: {bucket}")

    return {
        "valid": not errors,
        "scope": "process_local",
        "thread_safe": True,
        "snapshot_immutable": True,
        "bounded_code_labels": True,
        "bounded_sqlstate_labels": True,
        "reviewed_code_count": 4,
        "pool_timeout_code": "database_pool_timeout",
        "controlled_pressure_timeout_count": 24,
        "controlled_pressure_zero_mutation": True,
        "controlled_pressure_representative_capacity": False,
        "openmetrics_renderer": True,
        "openmetrics_prefix": "nutriflavor_database_recovery",
        "malformed_values_rejected": True,
        "sensitive_identifiers_recorded": False,
        "public_http_endpoint": False,
        "cross_replica_aggregation": False,
        "persistent_across_restart": False,
        "alert_evaluation": True,
        "exact_sensitive_name_validation": True,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
