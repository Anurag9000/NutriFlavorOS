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


def _require_fragments(
    errors: list[str],
    *,
    path: Path,
    fragments: set[str],
    label: str,
) -> str:
    if not path.is_file():
        return ""
    source = path.read_text(encoding="utf-8")
    for fragment in sorted(fragments):
        if fragment not in source:
            errors.append(f"{label} lacks required contract fragment: {fragment}")
    return source


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
        "frontend/src/App.tsx",
        "frontend/src/components/AppSidebar.tsx",
        "frontend/src/lib/preparationRepairApi.ts",
        "frontend/src/pages/PreparationRepairReview.tsx",
        "frontend/src/pages/PreparationRepairReview.test.tsx",
        "scripts/benchmark_preparation_repair.py",
        "scripts/repair_preparation_schedule.py",
        "docs/PREPARATION_REPAIR.md",
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
    engine_source = _require_fragments(
        errors,
        path=engine_path,
        label="repair engine",
        fragments={
            "immutable_task_infeasible",
            "immutable_dependency_not_pinned",
            "repair_infeasible",
            "deterministic_minimal_change_preparation_repair_v1",
            "Human review and explicit acceptance are required",
            "No execution event is inferred",
            "lexicographic unscheduled count",
        },
    )
    if engine_source:
        tree = ast.parse(engine_source, filename=str(engine_path))
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
    api_source = _require_fragments(
        errors,
        path=api_path,
        label="repair API",
        fragments={
            '"/schedule/repair"',
            "response_model=PreparationScheduleRepairResult",
            "repair_preparation_schedule(payload)",
            "status_code=409",
        },
    )
    if api_source:
        tree = ast.parse(api_source, filename=str(api_path))
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
    _require_fragments(
        errors,
        path=cli_path,
        label="repair CLI",
        fragments={
            '"persistence": "not_persisted"',
            '"human_acceptance_required": True',
            "repair_rejected",
        },
    )

    client_path = ROOT / "frontend/src/lib/preparationRepairApi.ts"
    client_source = _require_fragments(
        errors,
        path=client_path,
        label="repair frontend client",
        fragments={
            '"/preparation/schedule/repair"',
            "requires_human_acceptance: true",
            "accepted: false",
            "persistence_performed: false",
            "PreparationScheduleRepairRequest",
            "PreparationScheduleRepairResult",
        },
    )
    for forbidden in [
        "createSchedule(",
        ".approve(",
        ".complete(",
        ".cancel(",
        "localStorage",
        "sessionStorage",
    ]:
        if forbidden in client_source:
            errors.append(
                "repair frontend client contains forbidden mutation/storage "
                f"fragment: {forbidden}"
            )

    page_path = ROOT / "frontend/src/pages/PreparationRepairReview.tsx"
    page_source = _require_fragments(
        errors,
        path=page_path,
        label="repair review page",
        fragments={
            "Advisory schedule repair",
            "Human review boundary",
            "Compute advisory repair",
            "Task-by-task change ledger",
            "requires_human_acceptance",
            "result.accepted",
            "result.persistence_performed",
            "unaccepted, unpersisted, unapproved, and unexecuted",
            "Previous and repaired preparation task placements",
            "Export is a local file action only",
        },
    )
    for forbidden in [
        "preparationOperationsApi.createSchedule",
        "preparationOperationsApi.approve",
        "preparationOperationsApi.complete",
        "preparationOperationsApi.cancel",
        "preparationOperationsApi.invalidate",
    ]:
        if forbidden in page_source:
            errors.append(
                f"repair review page contains forbidden lifecycle action: {forbidden}"
            )

    app_path = ROOT / "frontend/src/App.tsx"
    _require_fragments(
        errors,
        path=app_path,
        label="frontend route",
        fragments={
            'import("./pages/PreparationRepairReview")',
            'path="/preparation/operations/repair"',
            "<ProtectedRoute>",
        },
    )

    sidebar_path = ROOT / "frontend/src/components/AppSidebar.tsx"
    _require_fragments(
        errors,
        path=sidebar_path,
        label="frontend navigation",
        fragments={
            'title: "Schedule Repair Review"',
            'url: "/preparation/operations/repair"',
        },
    )

    test_path = ROOT / "frontend/src/pages/PreparationRepairReview.test.tsx"
    _require_fragments(
        errors,
        path=test_path,
        label="repair frontend test",
        fragments={
            "loads a replayable source without accepting or persisting anything",
            "submits exact previous evidence, revised problem, strategy, and immutable tasks",
            "renders an accessible change ledger and explicit advisory flags",
            "keeps export disabled until the user reviews changes and the boundary",
            "does not offer completed schedules as repairable inputs",
        },
    )

    return {
        "valid": not errors,
        "strategies": [value.value for value in PreparationRepairStrategy],
        "required_files": required_files,
        "repair_api_path": "/api/v1/preparation/schedule/repair",
        "repair_frontend_path": "/preparation/operations/repair",
        "advisory_fields": sorted(required_result_fields),
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
