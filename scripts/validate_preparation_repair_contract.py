#!/usr/bin/env python3
"""Validate the deterministic preparation-repair implementation contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.domain.preparation_repair import (
    PreparationRepairStrategy,
    PreparationScheduleRepairRequest,
    PreparationScheduleRepairResult,
)
from backend.engines.prep_schedule_repair import (
    PreparationRepairError,
    repair_preparation_schedule,
)


ROOT = Path(__file__).resolve().parents[1]


def validate_contract() -> dict:
    errors: list[str] = []
    required_files = [
        "backend/domain/preparation_repair.py",
        "backend/engines/prep_schedule_repair.py",
        "backend/tests/test_preparation_schedule_repair.py",
        "backend/tests/test_preparation_repair_benchmark.py",
        "backend/tests/test_preparation_repair_cli.py",
        "scripts/benchmark_preparation_repair.py",
        "scripts/repair_preparation_schedule.py",
        ".github/workflows/preparation-repair.yml",
    ]
    for relative in required_files:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required repair file: {relative}")

    if sorted(value.value for value in PreparationRepairStrategy) != [
        "bounded_exact_min_change",
        "greedy_min_change",
    ]:
        errors.append("repair strategy enum drifted")
    if not callable(repair_preparation_schedule):
        errors.append("repair_preparation_schedule is not callable")
    if not issubclass(PreparationRepairError, ValueError):
        errors.append("PreparationRepairError must remain a fail-closed ValueError")
    if "previous_request" not in PreparationScheduleRepairRequest.model_fields:
        errors.append("repair request no longer carries the previous request")
    if "immutable_task_ids" not in PreparationScheduleRepairRequest.model_fields:
        errors.append("repair request no longer carries immutable task IDs")
    if "response" not in PreparationScheduleRepairResult.model_fields:
        errors.append("repair result no longer carries the deterministic response")

    engine_path = ROOT / "backend/engines/prep_schedule_repair.py"
    if engine_path.is_file():
        source = engine_path.read_text(encoding="utf-8")
        required_fragments = {
            "immutable_task_infeasible",
            "immutable_dependency_not_pinned",
            "repair_infeasible",
            "deterministic_minimal_change_preparation_repair_v1",
            "Human review and explicit acceptance are required",
            "No execution event is inferred",
            "lexicographic unscheduled count",
        }
        for fragment in sorted(required_fragments):
            if fragment not in source:
                errors.append(f"repair engine lacks required contract fragment: {fragment}")
        tree = ast.parse(source, filename=str(engine_path))
        forbidden_calls = {
            "commit",
            "flush",
            "execute",
            "add",
            "add_all",
            "delete",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden_calls:
                    errors.append(
                        f"repair engine contains persistence-like call {node.func.attr} at line {node.lineno}"
                    )

    cli_path = ROOT / "scripts/repair_preparation_schedule.py"
    if cli_path.is_file():
        source = cli_path.read_text(encoding="utf-8")
        for fragment in [
            '"persistence": "not_persisted"',
            '"human_acceptance_required": True',
            "repair_rejected",
        ]:
            if fragment not in source:
                errors.append(f"repair CLI lacks required fragment: {fragment}")

    return {
        "valid": not errors,
        "strategies": [value.value for value in PreparationRepairStrategy],
        "required_files": required_files,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
