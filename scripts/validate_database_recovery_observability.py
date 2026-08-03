#!/usr/bin/env python3
"""Validate privacy-preserving database recovery observability."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "metrics": "backend/database_recovery_metrics.py",
    "handler": "backend/api/database_error_handlers.py",
    "retry": "backend/exact_database_retry.py",
    "tests": "backend/tests/test_database_recovery_metrics.py",
    "repair_workflow": ".github/workflows/preparation-repair.yml",
    "postgres_workflow": ".github/workflows/preparation-repair-postgres.yml",
    "docs": "docs/DATABASE_RECOVERY_OBSERVABILITY.md",
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
            '"08xxx"',
            '"unknown"',
            "record_retry_succeeded_after_retry",
            "record_retry_exhausted",
            "record_utility_outcome_unknown",
            "RLock()",
        },
        "handler": {
            "from backend.database_recovery_metrics import DATABASE_RECOVERY_METRICS",
            "DATABASE_RECOVERY_METRICS.record_operational_error(",
            "connection_invalidated=bool(exc.connection_invalidated)",
            '"automatic_retry_performed": False',
        },
        "retry": {
            "from backend.database_recovery_metrics import DATABASE_RECOVERY_METRICS",
            "DATABASE_RECOVERY_METRICS.record_retry_observation(",
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
        "repair_workflow": {
            "backend/database_recovery_metrics.py",
            "backend/tests/test_database_recovery_metrics.py",
            "validate_database_recovery_observability.py",
        },
        "postgres_workflow": {
            "backend/database_recovery_metrics.py",
            "backend/tests/test_database_recovery_metrics.py",
            "validate_database_recovery_observability.py",
        },
        "docs": {
            "Database Recovery Observability",
            "never receives or stores SQL text",
            "retry_success_after_retry_total",
            "outcome-unknown events: critical",
            "1,600 concurrent updates",
            "no unauthenticated HTTP metrics endpoint",
        },
        "status": {
            "database recovery observability",
            "privacy-preserving process metrics",
        },
        "roadmap": {
            "database recovery observability",
            "cross-replica aggregation",
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

    forbidden_main = {
        "database-recovery-metrics",
        "DATABASE_RECOVERY_METRICS.snapshot",
        "snapshot_database_recovery_metrics",
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
    for fragment in sorted(forbidden_metrics):
        if fragment in sources["metrics"]:
            errors.append(f"metrics core contains forbidden surface: {fragment}")

    return {
        "valid": not errors,
        "scope": "process_local",
        "thread_safe": True,
        "snapshot_immutable": True,
        "bounded_code_labels": True,
        "bounded_sqlstate_labels": True,
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
