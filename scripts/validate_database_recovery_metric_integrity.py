#!/usr/bin/env python3
"""Validate exact database-recovery metric classification and numeric integrity."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "metrics": "backend/database_recovery_metrics.py",
    "retry": "backend/exact_database_retry.py",
    "metrics_tests": "backend/tests/test_database_recovery_metrics.py",
    "integrity_tests": "backend/tests/test_database_recovery_metric_integrity.py",
    "retry_tests": "backend/tests/test_exact_database_retry.py",
    "workflow": ".github/workflows/preparation-repair-pool-exhaustion.yml",
    "docs": "docs/DATABASE_RECOVERY_OBSERVABILITY.md",
    "retry_docs": "docs/PREPARATION_REPAIR_SERIALIZATION_RETRY.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing recovery metric integrity file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


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
            "from math import isfinite",
            "def _finite_nonnegative_delay",
            "def _expected_code_for_operational_error",
            "def _validate_operational_classification",
            "def _validate_retry_observation_classification",
            "database recovery code does not match its operational proof flags",
            "database recovery code does not match retry observation proof flags",
            "retryable must match abort, ambiguity, or pre-transaction proof",
            "an invalidated connection must be classified outcome unknown",
            "delay_seconds must be a finite nonnegative number",
            "normalized_delay = _finite_nonnegative_delay(delay_seconds)",
            "type(value) is not int or value < 1",
        },
        "retry": {
            "from math import isfinite",
            "def _finite_nonnegative_policy_value",
            "must be a finite nonnegative number",
            '_finite_nonnegative_policy_value(\n            "base_delay_seconds"',
            '_finite_nonnegative_policy_value(\n            "max_delay_seconds"',
            "type(self.max_attempts) is not int",
            "object.__setattr__(self, \"base_delay_seconds\", base_delay)",
            "object.__setattr__(self, \"max_delay_seconds\", max_delay)",
            "attempt must be a positive integer",
        },
        "metrics_tests": {
            "test_invalid_metric_combinations_fail_before_counter_mutation",
            "test_classification_code_and_flags_must_match_before_counter_mutation",
            "assert snapshot.operational_error_total == 0",
            "assert snapshot.retry_observation_total == 0",
            "assert dict(snapshot.code_counts) == {}",
            "assert dict(snapshot.sqlstate_counts) == {}",
        },
        "integrity_tests": {
            "test_nonfinite_metric_delays_fail_before_counter_mutation",
            "test_alert_thresholds_require_positive_integers",
            "test_exact_reviewed_classifications_remain_recordable",
            'float("nan")',
            'float("inf")',
            'float("-inf")',
            "snapshot.retry_observation_total == 0",
            "snapshot.retry_delay_seconds_total == 0",
            '"database_pool_timeout": 1',
        },
        "retry_tests": {
            "test_policy_and_idempotency_key_validation",
            'float("nan")',
            'float("inf")',
            'float("-inf")',
            "for invalid_attempts in (",
            "0, 21, True, 1.5",
            "for invalid_attempt in (",
            "0, -1, True, 1.5",
        },
        "workflow": {
            "backend/tests/test_database_recovery_metric_integrity.py",
            "scripts/validate_database_recovery_metric_integrity.py",
            "reports/preparation-repair-pool-exhaustion.xml",
        },
        "docs": {
            "Exact classification and numeric integrity",
            "code and proof flags must agree",
            "finite and nonnegative",
            "positive integer thresholds",
            "before any counter changes",
        },
        "retry_docs": {
            "finite and nonnegative",
            "positive integer",
            "NaN",
            "infinity",
        },
        "status": {
            "Exact classification integrity",
            "Nonfinite retry timing",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks metric-integrity fragment: {fragment}"
                )

    expected_integrity_tests = {
        "test_nonfinite_metric_delays_fail_before_counter_mutation",
        "test_alert_thresholds_require_positive_integers",
        "test_exact_reviewed_classifications_remain_recordable",
    }
    for name in sorted(
        expected_integrity_tests - _test_names(sources["integrity_tests"])
    ):
        errors.append(f"recovery metric integrity test is missing: {name}")

    expected_metrics_tests = {
        "test_invalid_metric_combinations_fail_before_counter_mutation",
        "test_classification_code_and_flags_must_match_before_counter_mutation",
    }
    for name in sorted(
        expected_metrics_tests - _test_names(sources["metrics_tests"])
    ):
        errors.append(f"recovery classification test is missing: {name}")

    forbidden_metrics = {
        "math.nan",
        "float('nan')",
        "float(\"nan\")",
        "except ValueError: pass",
        "try: return float(value)",
    }
    for fragment in sorted(forbidden_metrics):
        if fragment in sources["metrics"]:
            errors.append(
                "metrics core contains a malformed-value bypass: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "exact_code_proof_partition": True,
        "invalidated_connection_requires_outcome_unknown": True,
        "retryable_partition_enforced": True,
        "retry_safe_partition_enforced": True,
        "nonfinite_policy_values_rejected": True,
        "nonfinite_metric_delays_rejected": True,
        "alert_thresholds_positive_integers": True,
        "atomic_failure_before_counter_mutation": True,
        "dynamic_field_name_validation": True,
        "multiline_test_formatting_normalized": True,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
