#!/usr/bin/env python3
"""Ensure only the authoritative repair-proposal creation service is callable."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_MODULE = (
    "backend.services.preparation_repair_proposal_creation_service"
)
LEGACY_MODULE = "backend.services.preparation_repair_proposal_service"
LEGACY_DEFINITION = (
    ROOT / "backend/services/preparation_repair_proposal_service.py"
)


def validate_creation_authority() -> dict:
    errors: list[str] = []
    inspected: list[str] = []
    roots = [ROOT / "backend", ROOT / "scripts"]
    for base in roots:
        for path in sorted(base.rglob("*.py")):
            if path == LEGACY_DEFINITION or path == Path(__file__).resolve():
                continue
            relative = path.relative_to(ROOT).as_posix()
            inspected.append(relative)
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
            aliases: set[str] = set()
            legacy_modules: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module == LEGACY_MODULE:
                        for alias in node.names:
                            if alias.name == "create_repair_proposal":
                                errors.append(
                                    f"{relative}:{node.lineno} imports legacy create_repair_proposal"
                                )
                    if node.module == AUTHORITATIVE_MODULE:
                        for alias in node.names:
                            if alias.name == "create_repair_proposal":
                                aliases.add(alias.asname or alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == LEGACY_MODULE:
                            legacy_modules.add(alias.asname or alias.name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id in legacy_modules
                        and node.func.attr == "create_repair_proposal"
                    ):
                        errors.append(
                            f"{relative}:{node.lineno} calls legacy create_repair_proposal"
                        )
            if relative == "backend/api/preparation_repair_proposal_routes.py":
                if "create_repair_proposal" not in aliases:
                    errors.append(
                        "proposal API does not import authoritative create_repair_proposal"
                    )

    return {
        "valid": not errors,
        "authoritative_module": AUTHORITATIVE_MODULE,
        "legacy_module": LEGACY_MODULE,
        "inspected_file_count": len(inspected),
        "errors": errors,
    }


def main() -> int:
    report = validate_creation_authority()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
