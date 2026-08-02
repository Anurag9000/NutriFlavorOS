#!/usr/bin/env python3
"""Validate the safe idempotency-key boundary for repaired-draft acceptance."""

from __future__ import annotations

import json
from pathlib import Path

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
)


ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "backend/tests/test_preparation_repair_acceptance_contract_boundaries.py"


def validate_boundary() -> dict:
    errors: list[str] = []
    field = PreparationRepairProposalAcceptRequest.model_fields["idempotency_key"]
    metadata = {type(item).__name__: item for item in field.metadata}
    maximum = getattr(metadata.get("MaxLen"), "max_length", None)
    if maximum != 160:
        errors.append(f"acceptance idempotency-key maximum is {maximum}, expected 160")

    if not TEST.is_file():
        errors.append("missing acceptance key boundary tests")
        test_source = ""
    else:
        test_source = TEST.read_text(encoding="utf-8")
    for fragment in [
        "test_acceptance_key_at_safe_maximum_is_valid",
        "test_acceptance_key_above_safe_maximum_is_rejected",
        '"a" * 160',
        '"a" * 161',
    ]:
        if fragment not in test_source:
            errors.append(f"acceptance key boundary test lacks: {fragment}")

    return {
        "valid": not errors,
        "maximum_idempotency_key_length": maximum,
        "test": str(TEST.relative_to(ROOT)),
        "errors": errors,
    }


def main() -> int:
    report = validate_boundary()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
