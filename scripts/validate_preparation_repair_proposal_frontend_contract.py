#!/usr/bin/env python3
"""Compatibility entry point for repair proposal frontend validation."""

from __future__ import annotations

import json

if __package__:
    from scripts.validate_preparation_repair_acceptance_frontend import (
        validate_frontend_acceptance,
    )
else:
    # GitHub Actions executes this file directly as
    # ``python scripts/validate_preparation_repair_proposal_frontend_contract.py``.
    # In that mode Python places ``scripts/`` rather than the repository root at
    # the front of ``sys.path``, so the package-qualified import is unavailable.
    from validate_preparation_repair_acceptance_frontend import (
        validate_frontend_acceptance,
    )


def validate_frontend_contract() -> dict:
    return validate_frontend_acceptance()


def main() -> int:
    report = validate_frontend_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
