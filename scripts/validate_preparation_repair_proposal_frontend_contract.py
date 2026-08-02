#!/usr/bin/env python3
"""Validate the typed frontend boundary for repair proposals."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "frontend/src/lib/preparationRepairProposalApi.ts"
TEST = ROOT / "frontend/src/lib/preparationRepairProposalApi.test.ts"


def validate_frontend_contract() -> dict:
    errors: list[str] = []
    for path in [CLIENT, TEST]:
        if not path.is_file():
            errors.append(f"missing frontend repair proposal file: {path.relative_to(ROOT)}")
    client = CLIENT.read_text(encoding="utf-8") if CLIENT.is_file() else ""
    test = TEST.read_text(encoding="utf-8") if TEST.is_file() else ""

    for fragment in [
        "accepted: false",
        "schedule_persistence_performed: false",
        "acknowledge_non_acceptance: true",
        "acknowledge_non_persistence: true",
        '"/reject"',
        "create:",
        "list:",
        "get:",
        "events:",
        "reject:",
    ]:
        if fragment not in client:
            errors.append(f"proposal frontend client lacks fragment: {fragment}")

    forbidden = [
        "accept:",
        "approve:",
        "persist:",
        "complete:",
        "execute:",
        "localStorage",
        "sessionStorage",
    ]
    for fragment in forbidden:
        if fragment in client:
            errors.append(f"proposal frontend client exposes forbidden fragment: {fragment}")

    for fragment in [
        "does not expose accept, approve, persist, complete, or execute methods",
        'expect(methods).toEqual(["create", "list", "get", "events", "reject"])',
        "encodes repeated status filters deterministically",
        "acknowledge_non_acceptance: true as const",
        "acknowledge_non_persistence: true as const",
    ]:
        if fragment not in test:
            errors.append(f"proposal frontend test lacks fragment: {fragment}")

    return {
        "valid": not errors,
        "client": str(CLIENT.relative_to(ROOT)),
        "test": str(TEST.relative_to(ROOT)),
        "implemented_methods": ["create", "list", "get", "events", "reject"],
        "errors": errors,
    }


def main() -> int:
    report = validate_frontend_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
