#!/usr/bin/env python3
"""Validate proactive task-execution eligibility gating in the frontend."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "client": "frontend/src/lib/preparationTaskExecutionEligibilityApi.ts",
    "client_test": "frontend/src/lib/preparationTaskExecutionEligibilityApi.test.ts",
    "page": "frontend/src/pages/PreparationTaskExecution.tsx",
    "page_test": "frontend/src/pages/PreparationTaskExecution.test.tsx",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing eligibility frontend file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "client": {
            "PreparationTaskExecutionEligibilityView",
            "source_schedule_has_accepted_replacement",
            "accepted_proposal_id",
            "acceptance_id",
            "replacement_schedule_id",
            "replacement_schedule_status",
            "replacement_schedule_version",
            "task-execution-eligibility",
            "get:",
        },
        "client_test": {
            "reads the authenticated schedule eligibility evidence",
            "exposes no mutation method",
            'toEqual(["get"])',
        },
        "page": {
            "preparationTaskExecutionEligibilityApi.get",
            "assertExecutionEligible",
            "eligibility?.eligible === true",
            "Execution blocked by accepted replacement",
            "accepted_proposal_id",
            "acceptance_id",
            "replacement_schedule_id",
            "Open replacement schedule",
            "Task controls remain disabled until the authoritative eligibility",
        },
        "page_test": {
            "loads explicit state and authoritative eligibility without mutation",
            "blocks a source after accepted replacement and exposes exact identities",
            "enables schedule completion only when terminal and eligible",
            "repair proposal #31",
            "acceptance #41",
            "replacement schedule #17",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks required fragment: {fragment}")

    for fragment in [
        "localStorage",
        "sessionStorage",
        "start:",
        "complete:",
        "skip:",
        "approve:",
        "persist:",
    ]:
        if fragment in sources["client"]:
            errors.append(f"eligibility client contains forbidden fragment: {fragment}")

    if "eligibility?.eligible === true" not in sources["page"]:
        errors.append("execution controls are not positively gated by eligibility")
    if "assertExecutionEligible();" not in sources["page"]:
        errors.append("mutation functions do not reassert eligibility before submission")

    return {
        "valid": not errors,
        "client": FILES["client"],
        "page": FILES["page"],
        "boundary": "read_before_mutate",
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
