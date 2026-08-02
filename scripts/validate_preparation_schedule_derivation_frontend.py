#!/usr/bin/env python3
"""Validate the protected read-only schedule derivation inspector."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "app": "frontend/src/App.tsx",
    "sidebar": "frontend/src/components/AppSidebar.tsx",
    "client": "frontend/src/lib/preparationScheduleDerivationApi.ts",
    "client_test": "frontend/src/lib/preparationScheduleDerivationApi.test.ts",
    "page": "frontend/src/pages/PreparationScheduleDerivation.tsx",
    "page_test": "frontend/src/pages/PreparationScheduleDerivation.test.tsx",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing derivation frontend file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


def validate_frontend() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "app": {
            'import("./pages/PreparationScheduleDerivation")',
            'path="/preparation/operations/derivation"',
            "<ProtectedRoute>",
        },
        "sidebar": {
            'title: "Schedule Derivation"',
            'url: "/preparation/operations/derivation"',
        },
        "client": {
            "PreparationScheduleDerivationEvidenceView",
            "source_repair_proposal_id",
            "source_repair_acceptance_id",
            "repair_request_hash",
            "repair_result_hash",
            "revised_request_hash",
            "repaired_response_hash",
            "/${scheduleId}/derivation",
            "get:",
        },
        "client_test": {
            "reads viewer-authorized schedule derivation evidence",
            "exposes no mutation method",
        },
        "page": {
            "Schedule derivation evidence",
            "Original deterministic scheduler",
            "Accepted repair chain",
            "No repair proposal or acceptance applies",
            "preparationScheduleDerivationApi.get",
            "read-only provenance",
        },
        "page_test": {
            "shows original scheduler evidence without fabricated repair links",
            "shows the full accepted repair chain",
            "reloads schedule and derivation scope after household change",
            "surfaces fail-closed derivation errors",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks derivation fragment: {fragment}")

    for forbidden in [
        "method: \"POST\"",
        "method: \"PUT\"",
        "method: \"PATCH\"",
        "method: \"DELETE\"",
        "localStorage",
        "sessionStorage",
    ]:
        if forbidden in sources["client"] or forbidden in sources["page"]:
            errors.append(f"derivation frontend contains mutation/storage: {forbidden}")

    return {
        "valid": not errors,
        "route": "/preparation/operations/derivation",
        "client_methods": ["get"],
        "errors": errors,
    }


def main() -> int:
    report = validate_frontend()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
