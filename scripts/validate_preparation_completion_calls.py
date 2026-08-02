#!/usr/bin/env python3
"""Reject new production callers of the low-level schedule completion transition."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
ALLOWED_LOW_LEVEL_COMPLETION_CALLERS = {
    Path("backend/services/preparation_task_completion_service.py"),
}


def _attribute_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _attribute_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _is_completed_event(node: ast.AST) -> bool:
    name = _attribute_name(node)
    return name in {
        "PreparationScheduleEventType.COMPLETED",
        "backend.domain.preparation_operations.PreparationScheduleEventType.COMPLETED",
    }


def validate_completion_callers() -> dict:
    violations: list[dict] = []
    inspected = 0
    for path in sorted(BACKEND.rglob("*.py")):
        relative = path.relative_to(ROOT)
        if "tests" in relative.parts or "migrations" in relative.parts:
            continue
        inspected += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _attribute_name(node.func)
            if callee not in {"transition_schedule", "preparation_operations_service.transition_schedule"}:
                continue
            event_keyword = next(
                (
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg == "event_type"
                ),
                None,
            )
            if event_keyword is None or not _is_completed_event(event_keyword):
                continue
            if relative not in ALLOWED_LOW_LEVEL_COMPLETION_CALLERS:
                violations.append(
                    {
                        "path": str(relative),
                        "line": node.lineno,
                        "callee": callee,
                    }
                )
    return {
        "valid": not violations,
        "inspected_python_files": inspected,
        "allowed_callers": sorted(str(value) for value in ALLOWED_LOW_LEVEL_COMPLETION_CALLERS),
        "violations": violations,
    }


def main() -> int:
    report = validate_completion_callers()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
