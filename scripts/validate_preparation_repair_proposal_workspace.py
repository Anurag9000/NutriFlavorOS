#!/usr/bin/env python3
"""Validate the protected repair proposal and draft-acceptance workspace."""

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
            "preparationRepairProposalApi.acceptance",
            "preparationRepairProposalApi.accept",
            "preparationRepairProposalApi.reject",
            "acknowledge_non_acceptance: true",
            "acknowledge_non_persistence: true",
            "acknowledge_creates_new_draft_only: true",
            "required_acknowledgement_task_ids",
            "exactAcknowledgements",
            "Two explicit lifecycle decisions",
            "Owner approval still required",
            "Review draft for approval",
            'selected.status === "proposed"',
            'selected.status === "accepted"',
        },
        "test": {
            "requires both advisory acknowledgements before proposal creation",
            "requires every changed task, a reason, and draft-only confirmation",
            "submits every exact proposal hash when accepting",
            "shows immutable accepted draft evidence without auto-approval",
            "keeps viewers read-only",
            "blocks acceptance controls for stale proposals",
        },
        "client": {
            "PreparationRepairProposalAcceptRequest",
            "PreparationRepairProposalAcceptanceView",
            "PreparationRepairProposalAcceptedDraftView",
            "approval_performed: false",
            "execution_performed: false",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in source.get(label, ""):
                errors.append(f"{FILES[label]} lacks workspace fragment: {fragment}")

    page = source.get("page", "")
    for forbidden in [
        "preparationRepairProposalApi.approve",
        "preparationOperationsApi.approve",
        "preparationOperationsApi.complete",
        "preparationOperationsApi.task",
        "localStorage",
        "sessionStorage",
    ]:
        if forbidden in page:
            errors.append(f"proposal workspace contains unrelated mutation: {forbidden}")

    route = 'path="/preparation/operations/repair-proposals"'
    app = source.get("app", "")
    route_index = app.find(route)
    protected_index = app.find("<ProtectedRoute>", route_index)
    page_index = app.find("<PreparationRepairProposals />", route_index)
    if route_index < 0 or protected_index < 0 or page_index < 0:
        errors.append("proposal registry route is not protected and page-bound")

    return {
        "valid": not errors,
        "route": "/preparation/operations/repair-proposals",
        "implemented_mutations": ["create", "accept", "reject"],
        "separate_lifecycle_actions": ["owner_approval", "task_execution", "completion"],
        "errors": errors,
    }


def main() -> int:
    report = validate_workspace()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
