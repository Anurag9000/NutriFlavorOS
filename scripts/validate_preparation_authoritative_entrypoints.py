#!/usr/bin/env python3
"""Validate authoritative preparation route/service and frontend entry points."""

from __future__ import annotations

import json
from pathlib import Path

from backend.api import preparation_operations_routes
from backend.services import preparation_operations_coverage_service
from backend.services import preparation_task_completion_service


ROOT = Path(__file__).resolve().parents[1]


def _package_entry(module, expected: str, symbol: str, errors: list[str]) -> None:
    path = Path(module.__file__).resolve()
    if path.name != "__init__.py" or path.parent.name != expected:
        errors.append(
            f"{module.__name__} resolved to {path.relative_to(ROOT)} instead of authoritative package {expected}"
        )
    if not callable(getattr(module, symbol, None)) and symbol != "router":
        errors.append(f"{module.__name__} does not export callable {symbol}")
    if symbol == "router" and getattr(module, symbol, None) is None:
        errors.append(f"{module.__name__} does not export router")


def validate_authoritative_entrypoints() -> dict:
    errors: list[str] = []
    _package_entry(
        preparation_operations_routes,
        "preparation_operations_routes",
        "router",
        errors,
    )
    _package_entry(
        preparation_operations_coverage_service,
        "preparation_operations_coverage_service",
        "get_preparation_operations_coverage",
        errors,
    )
    _package_entry(
        preparation_task_completion_service,
        "preparation_task_completion_service",
        "complete_schedule_with_execution_guard",
        errors,
    )

    route_source = (
        ROOT / "backend" / "api" / "preparation_operations_routes" / "__init__.py"
    ).read_text(encoding="utf-8")
    required_route_fragments = {
        "validate_occurrence_set_against_approved_plan",
        "preparation_task_execution_authoritative_service",
        "complete_schedule_with_execution_guard",
        "get_preparation_operations_coverage",
    }
    for fragment in sorted(required_route_fragments):
        if fragment not in route_source:
            errors.append(f"authoritative preparation routes lack {fragment}")

    execution_shim = (
        ROOT / "frontend" / "src" / "pages" / "PreparationTaskExecution.ts"
    ).read_text(encoding="utf-8")
    if '"./PreparationTaskExecutionV2"' not in execution_shim:
        errors.append("task execution shim does not route to PreparationTaskExecutionV2")

    operations_shim = (
        ROOT / "frontend" / "src" / "pages" / "PreparationOperations.ts"
    ).read_text(encoding="utf-8")
    if '"./PreparationOperationsV2"' not in operations_shim:
        errors.append("preparation operations shim does not route to PreparationOperationsV2")

    structured_source = (
        ROOT / "frontend" / "src" / "pages" / "PreparationOperationsV2.tsx"
    ).read_text(encoding="utf-8")
    required_review_fragments = {
        "Structured persistence review",
        "Required confirmations",
        "Read-only canonical bundle JSON",
        "Persist reviewed schedule draft",
        "schedule_response.unscheduled",
        "profile_versions",
    }
    for fragment in sorted(required_review_fragments):
        if fragment not in structured_source:
            errors.append(f"structured operations review lacks {fragment}")
    if 'aria-label="Schedule bundle JSON"' not in structured_source:
        errors.append("structured operations review lacks canonical JSON inspection")

    return {
        "valid": not errors,
        "authoritative_route_module": preparation_operations_routes.__file__,
        "authoritative_coverage_module": preparation_operations_coverage_service.__file__,
        "authoritative_completion_module": preparation_task_completion_service.__file__,
        "errors": errors,
    }


def main() -> int:
    report = validate_authoritative_entrypoints()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
