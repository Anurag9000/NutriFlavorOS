#!/usr/bin/env python3
"""Reject obsolete unsupported repository-level product and model claims."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES: Dict[str, List[str]] = {
    "AUDIT_SUMMARY.md": [
        "experimental household food-planning and preparation platform",
        "not certified or demonstrated as production ready",
        "not a medical device",
        "green CI for the exact commit",
    ],
    "ML_MODELS_INVENTORY.md": [
        "research and experimental implementations",
        "is not evidence that a model has been trained",
        "Required evidence per learned model",
        "Prohibited inventory labels without evidence",
    ],
    "FUTURE_ML_MODELS.md": [
        "experimental research roadmap",
        "deterministic or simple statistical baseline",
        "calibrated confidence, abstention, human override, rollback",
        "Deferred or prohibited proposals",
    ],
    "docs/EXHAUSTIVE_MISSION_AUDIT.md": [
        "Exhaustive workstream inventory",
        "Remaining work, ordered by priority",
        "Explicitly rejected or deferred claims",
        "Completion definition",
    ],
}

FORBIDDEN_EXACT: Dict[str, List[str]] = {
    "AUDIT_SUMMARY.md": [
        "✅ **Production Ready**",
        "### ✅ Ready for Production",
        "No security vulnerabilities found",
        "Deploy to production with confidence",
    ],
    "ML_MODELS_INVENTORY.md": [
        "**Status:** ✅ Production Ready | Trained to Convergence",
        "## 🧠 ML Models in Production",
        "**Accuracy Target**: 95%+",
        "**Simulations**: 10,000+ episodes",
        "The most intelligent, personalized, and engaging nutrition platform ever built",
    ],
    "FUTURE_ML_MODELS.md": [
        "Possible lactose intolerance (confidence: 78%)",
        "Therapist referral (if chronic)",
        "glucose spike risk: 85%",
        "20-30% improvement in sleep quality",
        "Viral growth +50%",
        "The most comprehensive AI nutrition platform ever built",
    ],
}


def validate_repository_claims(root: Path = ROOT) -> dict:
    failures: List[dict] = []
    checked: List[str] = []

    for relative_path, required_fragments in REQUIRED_FILES.items():
        path = root / relative_path
        if not path.is_file():
            failures.append(
                {
                    "path": relative_path,
                    "code": "required_file_missing",
                    "detail": "Required current-status document is absent",
                }
            )
            continue
        content = path.read_text(encoding="utf-8")
        checked.append(relative_path)
        for fragment in required_fragments:
            if fragment not in content:
                failures.append(
                    {
                        "path": relative_path,
                        "code": "required_boundary_missing",
                        "detail": fragment,
                    }
                )
        for fragment in FORBIDDEN_EXACT.get(relative_path, []):
            if fragment in content:
                failures.append(
                    {
                        "path": relative_path,
                        "code": "unsupported_legacy_claim_present",
                        "detail": fragment,
                    }
                )

    return {
        "valid": not failures,
        "checked_files": sorted(checked),
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> int:
    report = validate_repository_claims()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
