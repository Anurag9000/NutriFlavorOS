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
from backend.main import app


ROOT = Path(__file__).resolve().parents[1]


def validate_contract() -> dict:
    errors: list[str] = []
    required_files = [
        "backend/api/preparation_routes.py",
        "backend/domain/preparation_repair.py",
        "backend/engines/prep_schedule_repair.py",
        "backend/tests/test_preparation_schedule_repair.py",
        "backend/tests/test_preparation_repair_advisory_boundary.py",
        "backend/tests/test_preparation_repair_api.py",
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

    required_result_fields = {
        "response",
        "requires_human_acceptance",
        "accepted",
        "persistence_performed",
    }
    missing_result_fields = sorted(
        required_result_fields
        - set(PreparationScheduleRepairResult.model_fields)
    )
    if missing_result_fields:
        errors.append(
            "repair result lacks advisory boundary fields: "
            + ", ".join(missing_result_fields)
        )
    else:
        result_fields = PreparationScheduleRepairResult.model_fields
        if result_fields["requires_human_acceptance"].default is not True:
            errors.append("repair results must require human acceptance by default")
        if result_fields["accepted"].default is not False:
            errors.append("repair computation must not default to accepted")
        if result_fields["persistence_performed"].default is not False:
            errors.append("repair computation must not default to persisted")

    document = app.openapi()
    repair_operation = document.get("paths", {}).get(
        "/api/v1/preparation/schedule/repair",
        {},
    ).get("post")
    if not isinstance(repair_operation, dict):
        errors.append("authenticated repair POST is absent from OpenAPI")
    else:
        if not repair_operation.get("security"):
            errors.append("repair POST is not represented as authenticated")
        response_schema = (
            repair_operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if response_schema.get("$ref") != (
            "#/components/schemas/PreparationScheduleRepairResult"
        ):
            errors.append("repair POST response schema drifted")

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

    api_path = ROOT / "backend/api/preparation_routes.py"
    if api_path.is_file():
        source = api_path.read_text(encoding="utf-8")
        for fragment in [
            '"/schedule/repair"',
            "response_model=PreparationScheduleRepairResult",
            "repair_preparation_schedule(payload)",
            "status_code=409",
        ]:
            if fragment not in source:
                errors.append(f"repair API lacks required fragment: {fragment}")
        tree = ast.parse(source, filename=str(api_path))
        repair_functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "repair_preparation"
        ]
        if len(repair_functions) != 1:
            errors.append("repair API must expose one authoritative function")
        else:
            forbidden_calls = {
                "commit",
                "flush",
                "execute",
                "add",
                "add_all",
                "delete",
            }
            for node in ast.walk(repair_functions[0]):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in forbidden_calls:
                        errors.append(
                            "repair API contains persistence-like call "
                            f"{node.func.attr} at line {node.lineno}"
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
        "repair_api_path": "/api/v1/preparation/schedule/repair",
        "advisory_fields": sorted(required_result_fields),
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
