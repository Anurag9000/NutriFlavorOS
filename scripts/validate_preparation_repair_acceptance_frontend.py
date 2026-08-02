#!/usr/bin/env python3
"""Validate the typed repaired-draft acceptance frontend boundary."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "frontend/src/lib/preparationRepairProposalApi.ts"
CLIENT_TEST = ROOT / "frontend/src/lib/preparationRepairProposalApi.test.ts"
PAGE = ROOT / "frontend/src/pages/PreparationRepairProposals.tsx"
PAGE_TEST = ROOT / "frontend/src/pages/PreparationRepairProposals.test.tsx"


def _read(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        errors.append(f"missing frontend acceptance file: {path.relative_to(ROOT)}")
        return ""
    return path.read_text(encoding="utf-8")


def validate_frontend_acceptance() -> dict:
    errors: list[str] = []
    client = _read(CLIENT, errors)
    client_test = _read(CLIENT_TEST, errors)
    page = _read(PAGE, errors)
    page_test = _read(PAGE_TEST, errors)

    required_client = [
        "PreparationRepairProposalAcceptRequest",
        "PreparationRepairProposalAcceptanceView",
        "PreparationRepairProposalAcceptedDraftView",
        "expected_proposal_version",
        "expected_source_schedule_hash",
        "expected_repair_request_hash",
        "expected_repair_result_hash",
        "expected_revised_request_hash",
        "expected_repaired_response_hash",
        "acknowledged_task_ids",
        "acknowledge_creates_new_draft_only: true",
        "created_schedule_status: \"draft\"",
        "approval_performed: false",
        "execution_performed: false",
        "acceptance:",
        "accept:",
    ]
    for fragment in required_client:
        if fragment not in client:
            errors.append(f"proposal client lacks acceptance fragment: {fragment}")

    required_page = [
        "Two explicit lifecycle decisions",
        "Accept and create draft",
        "Required changed-task acknowledgements",
        "acknowledge_creates_new_draft_only: true",
        "expected_repair_request_hash: selected.repair_request_hash",
        "expected_repair_result_hash: selected.repair_result_hash",
        "expected_revised_request_hash: selected.revised_request_hash",
        "expected_repaired_response_hash: selected.repaired_response_hash",
        "accepted draft evidence",
        "Owner approval still required",
        "Review draft for approval",
    ]
    page_lower = page.lower()
    for fragment in required_page:
        if fragment.lower() not in page_lower:
            errors.append(f"proposal page lacks acceptance fragment: {fragment}")

    required_tests = [
        "requires every changed task, a reason, and draft-only confirmation",
        "submits every exact proposal hash when accepting",
        "shows immutable accepted draft evidence without auto-approval",
        "keeps viewers read-only",
        "blocks acceptance controls for stale proposals",
        "accepts only through an exact new-draft request",
    ]
    combined_tests = client_test + page_test
    for fragment in required_tests:
        if fragment not in combined_tests:
            errors.append(f"frontend acceptance tests lack: {fragment}")

    disallowed_client_fragments = [
        "approve:",
        "complete:",
        "localStorage",
        "sessionStorage",
    ]
    for fragment in disallowed_client_fragments:
        if fragment in client:
            errors.append(f"proposal client contains unrelated lifecycle method: {fragment}")

    return {
        "valid": not errors,
        "client": str(CLIENT.relative_to(ROOT)),
        "page": str(PAGE.relative_to(ROOT)),
        "errors": errors,
    }


def main() -> int:
    report = validate_frontend_acceptance()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
