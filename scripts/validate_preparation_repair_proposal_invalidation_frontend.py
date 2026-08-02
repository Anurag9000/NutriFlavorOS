#!/usr/bin/env python3
"""Validate typed owner proposal invalidation without proposal-side approval."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "frontend/src/lib/preparationRepairProposalApi.ts"
TEST = ROOT / "frontend/src/lib/preparationRepairProposalApi.test.ts"
DOC = ROOT / "docs/PREPARATION_REPAIR_PROPOSALS.md"


def _read(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        errors.append(f"missing invalidation frontend file: {path.relative_to(ROOT)}")
        return ""
    return path.read_text(encoding="utf-8")


def validate_frontend() -> dict:
    errors: list[str] = []
    client = _read(CLIENT, errors)
    test = _read(TEST, errors)
    doc = _read(DOC, errors)

    for fragment in {
        "PreparationRepairProposalInvalidateRequest",
        "acknowledge_historical_only: true",
        "invalidate:",
        '`${collection(householdId)}/${proposalId}/invalidate`',
        'method: "POST"',
    }:
        if fragment not in client:
            errors.append(f"proposal invalidation client lacks: {fragment}")

    for fragment in {
        "invalidates only through an explicit historical-only owner request",
        "acknowledge_historical_only: true as const",
        "repair-proposal-invalidate-client-0001",
        '"invalidate"',
        'methods).not.toContain("approve")',
        'methods).not.toContain("complete")',
        'methods).not.toContain("execute")',
    }:
        if fragment not in test:
            errors.append(f"proposal invalidation client test lacks: {fragment}")

    for fragment in {
        "Owner-only proposal invalidation",
        "primary owner administrative control remains a follow-on UI item",
    }:
        if fragment not in doc:
            errors.append(f"proposal invalidation documentation lacks: {fragment}")

    for fragment in {
        "approve:",
        "complete:",
        "execute:",
        "localStorage",
        "sessionStorage",
    }:
        if fragment in client:
            errors.append(f"proposal client contains forbidden action/storage: {fragment}")

    return {
        "valid": not errors,
        "client": str(CLIENT.relative_to(ROOT)),
        "ui_control_implemented": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_frontend()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
