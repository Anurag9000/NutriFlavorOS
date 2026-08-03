#!/usr/bin/env python3
"""Validate the protected preparation support export frontend boundary."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "client": "frontend/src/lib/preparationScheduleSupportExportApi.ts",
    "client_tests": "frontend/src/lib/preparationScheduleSupportExportApi.test.ts",
    "page": "frontend/src/pages/PreparationScheduleSupportExport.tsx",
    "page_tests": "frontend/src/pages/PreparationScheduleSupportExport.test.tsx",
    "app": "frontend/src/App.tsx",
    "layout": "frontend/src/components/AppLayout.tsx",
    "sidebar": "frontend/src/components/AppSidebar.tsx",
    "workflow": ".github/workflows/preparation-repair.yml",
    "docs": "docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing support export frontend file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "client": {
            "export interface PreparationScheduleSupportExport",
            'document_version: "preparation-schedule-support-export-v1"',
            "snapshot_read_only: true",
            "mutation_performed: false",
            "actual_execution_verified: false",
            "food_safety_verified: false",
            "export function supportExportFilename",
            "export function serializeSupportExport",
            "/support-export",
            "preparationScheduleSupportExportApi = {",
            "get:",
        },
        "client_tests": {
            "reads the viewer-authorized support export endpoint",
            "exposes no mutation method",
            "creates a filesystem-safe hash-addressed filename",
            "serializes the complete object with a trailing newline",
        },
        "page": {
            "Preparation schedule support export",
            "Generate read-only snapshot",
            "Generate fresh snapshot",
            "Download JSON evidence",
            "supportExportFilename(value)",
            "serializeSupportExport(value)",
            "URL.createObjectURL(blob)",
            "URL.revokeObjectURL(url)",
            "exportM.reset()",
            'aria-live="polite"',
            "Mutation performed: false",
            "Actual execution verified: false",
            "Food safety verified: false",
            "Nothing is generated automatically",
            "<AppLayout>",
        },
        "page_tests": {
            "does not generate evidence until the user explicitly requests it",
            "shows server identity, evidence counts, and non-claims",
            "downloads the complete JSON under a hash-addressed filename",
            "clears stale evidence when schedule scope changes",
            "surfaces fail-closed server errors without creating a download",
            "Object.defineProperty(URL, \"createObjectURL\"",
            "originalCreateObjectURL",
            "Reflect.deleteProperty(URL, \"createObjectURL\")",
        },
        "app": {
            "PreparationScheduleSupportExport",
            'path="/preparation/operations/support-export"',
            "<ProtectedRoute>",
        },
        "layout": {
            '<main id="main-content"',
            "{children}</main>",
        },
        "sidebar": {
            'title: "Support Evidence Export"',
            'url: "/preparation/operations/support-export"',
            "FileJson",
        },
        "workflow": {
            "preparationScheduleSupportExportApi.test.ts",
            "PreparationScheduleSupportExport.test.tsx",
            "validate_preparation_schedule_support_export_frontend.py",
        },
        "docs": {
            "Viewer-authorized API",
            "Operational CLI",
            "Protected browser workspace",
            "mutation_performed=false",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks frontend fragment: {fragment}")

    forbidden = {
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "preparationScheduleSupportExportApi.create",
        "preparationScheduleSupportExportApi.update",
        "preparationScheduleSupportExportApi.delete",
        "fetch(\"/api",
    }
    combined = "\n".join([sources["client"], sources["page"]])
    for fragment in sorted(forbidden):
        if fragment in combined:
            errors.append(f"support export frontend contains forbidden authority: {fragment}")

    for forbidden_landmark in {"<main", 'id="main-content"'}:
        if forbidden_landmark in sources["page"]:
            errors.append(
                "support export page duplicates the AppLayout main landmark: "
                f"{forbidden_landmark}"
            )

    return {
        "valid": not errors,
        "route": "/preparation/operations/support-export",
        "explicit_generation_required": True,
        "client_methods": ["get"],
        "browser_storage_used": False,
        "server_evidence_hash_preserved": True,
        "main_landmark_owner": "AppLayout",
        "mutation_performed": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
