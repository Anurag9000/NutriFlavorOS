#!/usr/bin/env python3
"""Audit product code for unguarded preparation schedule completion calls."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOW_LEVEL_MODULE = "backend.services.preparation_operations_service"
GUARDED_MODULE = "backend.services.preparation_task_completion_service"
ROUTES = ROOT / "backend/api/preparation_operations_routes.py"
COMPLETION_SERVICE = (
    ROOT / "backend/services/preparation_task_completion_service.py"
)


def _is_completed_expression(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value == "completed"
    if isinstance(node, ast.Attribute):
        return node.attr == "COMPLETED"
    return False


def _call_requests_completion(node: ast.Call) -> bool:
    for keyword in node.keywords:
        if keyword.arg in {"event_type", "to_status", "target_status"}:
            if _is_completed_expression(keyword.value):
                return True
    return False


def _scan_file(path: Path, errors: list[str]) -> None:
    relative = path.relative_to(ROOT).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative)
    low_level_aliases: set[str] = set()
    low_level_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == LOW_LEVEL_MODULE:
            for alias in node.names:
                if alias.name == "transition_schedule":
                    low_level_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == LOW_LEVEL_MODULE:
                    low_level_modules.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _call_requests_completion(node):
            continue
        direct = isinstance(node.func, ast.Name) and node.func.id in low_level_aliases
        qualified = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "transition_schedule"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in low_level_modules
        )
        if direct or qualified:
            errors.append(
                f"{relative}:{node.lineno} directly requests low-level schedule completion"
            )


def validate_completion_authority() -> dict:
    errors: list[str] = []
    inspected = 0
    for base in [ROOT / "backend/api", ROOT / "backend/services"]:
        for path in sorted(base.rglob("*.py")):
            if path == COMPLETION_SERVICE:
                continue
            _scan_file(path, errors)
            inspected += 1

    if not ROUTES.is_file():
        errors.append("missing preparation operations routes")
        route_source = ""
    else:
        route_source = ROUTES.read_text(encoding="utf-8")
    for fragment in [
        "complete_schedule_with_execution_guard",
        '"/{schedule_id}/complete"',
        "HouseholdRole.EDITOR",
    ]:
        if fragment not in route_source:
            errors.append(f"completion route lacks guarded fragment: {fragment}")

    if not COMPLETION_SERVICE.is_file():
        errors.append("missing task completion guard service")
        service_source = ""
    else:
        service_source = COMPLETION_SERVICE.read_text(encoding="utf-8")
        ast.parse(
            service_source,
            filename=str(COMPLETION_SERVICE.relative_to(ROOT)),
        )
    for fragment in [
        "def complete_schedule_with_execution_guard",
        "remaining_count",
        "transition_schedule(",
        "PreparationScheduleEventType.COMPLETED",
    ]:
        if fragment not in service_source:
            errors.append(f"task completion service lacks guarded fragment: {fragment}")

    return {
        "valid": not errors,
        "low_level_module": LOW_LEVEL_MODULE,
        "guarded_module": GUARDED_MODULE,
        "inspected_product_file_count": inspected,
        "errors": errors,
    }


def main() -> int:
    report = validate_completion_authority()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
