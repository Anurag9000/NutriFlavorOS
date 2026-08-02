#!/usr/bin/env python3
"""Validate the protected repair-proposal registry and its non-acceptance UI."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "app": "frontend/src/App.tsx",
    "sidebar": "frontend/src/components/AppSidebar.tsx",
    "page": "frontend/src/pages/PreparationRepairProposals.tsx",
    "test": "frontend/src/pages/PreparationRepairProposals.test.tsx",
    "client": "frontend/src/lib/preparationRepairProposalApi.ts",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing proposal workspace file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


def validate_workspace() -> dict:
    errors: list[str] = []
    source = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "app": {
            'import("./pages/PreparationRepairProposals")',
            'path="/preparation/operations/repair-proposals"',
            "<ProtectedRoute>",
        },
        "sidebar": {
            'title: "Repair Proposals"',
            'url: "/preparation/operations/repair-proposals"',
        },
        "page": {
            "Repair proposal registry",
            "preparationRepairProposalApi.create",
            "preparationRepairProposalApi.list",
            "preparationRepairProposalApi.events",
            "preparationRepairProposalApi.reject",
            "acknowledge_non_acceptance: true",
            "acknowledge_non_persistence: true",
            "required_acknowledgement_task_ids",
            "stale_reasons",
            "accepted=false",
            "schedule_persistence_performed=false",
            "Acceptance remains unavailable",
            'selected.status === "proposed"',
        },
        "test": {
            "requires both non-acceptance acknowledgements before creation",
            "submits exact source, calendar, revised request, and immutable tasks",
            "allows versioned rejection but not source mutation",
            "keeps viewers read-only",
            "surfaces execution-history staleness",
            "queryByRole(\"button\", { name: /^Accept/i })",
        },
        "client": {
            "accepted: false",
            "schedule_persistence_performed: false",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in source.get(label, ""):
                errors.append(f"{FILES[label]} lacks workspace fragment: {fragment}")

    page = source.get("page", "")
    for forbidden in [
        "preparationRepairProposalApi.accept",
        "preparationRepairProposalApi.approve",
        "preparationRepairProposalApi.persist",
        "preparationOperationsApi.approve",
        "preparationOperationsApi.complete",
        "preparationOperationsApi.task",
        "localStorage",
        "sessionStorage",
    ]:
        if forbidden in page:
            errors.append(f"proposal workspace contains forbidden mutation: {forbidden}")

    route = 'path="/preparation/operations/repair-proposals"'
    route_index = source.get("app", "").find(route)
    protected_index = source.get("app", "").find("<ProtectedRoute>", route_index)
    page_index = source.get("app", "").find("<PreparationRepairProposals />", route_index)
    if route_index < 0 or protected_index < 0 or page_index < 0:
        errors.append("proposal registry route is not protected and page-bound")

    return {
        "valid": not errors,
        "route": "/preparation/operations/repair-proposals",
        "implemented_mutations": ["create", "reject"],
        "forbidden_mutations": ["accept", "approve", "persist", "execute", "complete"],
        "errors": errors,
    }


def main() -> int:
    report = validate_workspace()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
