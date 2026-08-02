#!/usr/bin/env python3
"""Validate that repair proposals cannot ignore task-execution history."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "creation": "backend/services/preparation_repair_proposal_creation_service.py",
    "read": "backend/services/preparation_repair_proposal_read_service.py",
    "routes": "backend/api/preparation_repair_proposal_routes.py",
    "tests": "backend/tests/test_preparation_repair_proposal_execution_boundary.py",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing execution-boundary file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=relative)
    return source


def validate_execution_boundary() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "creation": {
            "DBPreparationTaskExecutionEvent",
            "repair_source_has_execution_history",
            "Execution-aware repair is not implemented",
            "DBPreparationTaskExecutionEvent.schedule_id == source.id",
        },
        "read": {
            "DBPreparationTaskExecutionEvent",
            "source_schedule_has_execution_history",
            "DBPreparationTaskExecutionEvent.schedule_id == source.id",
            "def _stale_reasons",
            "def _proposal_view",
        },
        "routes": {
            "preparation_repair_proposal_read_service",
            "get_repair_proposal",
            "list_repair_proposals",
            "reject_repair_proposal",
        },
        "tests": {
            "test_proposal_creation_rejects_source_with_task_execution_history",
            "test_existing_proposal_becomes_stale_when_execution_begins",
            '"repair_source_has_execution_history"',
            '"source_schedule_has_execution_history"',
        },
    }
    for label, fragments in required.items():
        source = sources.get(label, "")
        for fragment in sorted(fragments):
            if fragment not in source:
                errors.append(
                    f"{FILES[label]} lacks execution-boundary fragment: {fragment}"
                )

    route_source = sources.get("routes", "")
    if (
        "from backend.services.preparation_repair_proposal_service import (\n"
        "    get_repair_proposal" in route_source
    ):
        errors.append("proposal API imports legacy non-execution-aware reads")

    creation_source = sources.get("creation", "")
    history_check = creation_source.find("repair_source_has_execution_history")
    repair_call = creation_source.find("repair_preparation_schedule(repair_request)")
    if history_check < 0 or repair_call < 0 or history_check > repair_call:
        errors.append(
            "execution-history rejection must occur before repair computation"
        )

    return {
        "valid": not errors,
        "boundary": "no_repair_proposal_after_task_execution_history",
        "required_files": list(FILES.values()),
        "errors": errors,
    }


def main() -> int:
    report = validate_execution_boundary()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
