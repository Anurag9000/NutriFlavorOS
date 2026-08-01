#!/usr/bin/env python3
"""Verify catalog and capability state is independent of import order."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MARKER = "__NUTRIFLAVOR_CATALOG_SNAPSHOT__="
SCENARIOS = {
    "package_first": [
        "import backend.research",
    ],
    "catalog_first": [
        "import backend.research.catalog",
    ],
    "capabilities_first": [
        "import backend.research.capabilities",
    ],
    "extension_module_first": [
        "import backend.research.catalog_extensions",
    ],
    "explicit_extension_repeated": [
        "from backend.research.catalog_extensions import apply_catalog_extensions",
        "apply_catalog_extensions()",
        "apply_catalog_extensions()",
    ],
    "mixed_reimports": [
        "import importlib",
        "import backend.research.catalog as catalog_module",
        "import backend.research.capabilities",
        "import backend.research",
        "importlib.import_module('backend.research.catalog_extensions').apply_catalog_extensions()",
    ],
}


def _snapshot_program(statements: list[str]) -> str:
    return "\n".join(
        [
            *statements,
            "from backend.research.catalog import get_catalog",
            "from backend.research.capabilities import implementation_status",
            "catalog = get_catalog()",
            "capabilities = implementation_status()",
            "snapshot = {",
            "    'version': catalog.version,",
            "    'counts': {",
            "        'tasks': len(catalog.tasks),",
            "        'datasets': len(catalog.datasets),",
            "        'models': len(catalog.models),",
            "        'experiments': len(catalog.experiments),",
            "        'features': len(catalog.features),",
            "    },",
            "    'ids': {",
            "        'tasks': [value.id for value in catalog.tasks],",
            "        'datasets': [value.id for value in catalog.datasets],",
            "        'models': [value.id for value in catalog.models],",
            "        'experiments': [value.id for value in catalog.experiments],",
            "        'features': [value.id for value in catalog.features],",
            "    },",
            "    'capabilities': {",
            "        key: {",
            "            'status': value.get('status'),",
            "            'module': value.get('module'),",
            "            'symbol': value.get('symbol'),",
            "            'runtime_available': value.get('runtime_available'),",
            "            'runtime_enabled': value.get('runtime_enabled'),",
            "            'implementation_error': value.get('implementation_error'),",
            "        }",
            "        for key, value in sorted(capabilities.items())",
            "    },",
            "}",
            f"print({MARKER!r} + json.dumps(snapshot, sort_keys=True))",
        ]
    ).replace(
        "from backend.research.catalog import get_catalog",
        "import json\nfrom backend.research.catalog import get_catalog",
        1,
    )


def _run_scenario(name: str, statements: list[str]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), value]
        if (value := env.get("PYTHONPATH"))
        else [str(ROOT)]
    )
    env["PYTHONHASHSEED"] = "0"
    result = subprocess.run(
        [sys.executable, "-c", _snapshot_program(statements)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    marker_lines = [
        line[len(MARKER) :]
        for line in result.stdout.splitlines()
        if line.startswith(MARKER)
    ]
    if result.returncode != 0 or len(marker_lines) != 1:
        return {
            "scenario": name,
            "success": False,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "snapshot": None,
        }
    try:
        snapshot = json.loads(marker_lines[0])
    except json.JSONDecodeError as exc:
        return {
            "scenario": name,
            "success": False,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "snapshot": None,
            "parse_error": str(exc),
        }
    return {
        "scenario": name,
        "success": True,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "snapshot": snapshot,
    }


def validate_catalog_import_order() -> dict[str, Any]:
    results = {
        name: _run_scenario(name, statements)
        for name, statements in SCENARIOS.items()
    }
    errors: list[str] = []
    for name, value in results.items():
        if not value["success"]:
            errors.append(
                f"Catalog import scenario {name} failed with return code "
                f"{value['returncode']}: {value['stderr'].strip()}"
            )

    successful = {
        name: value["snapshot"]
        for name, value in results.items()
        if value["success"]
    }
    canonical_name = "package_first"
    canonical = successful.get(canonical_name)
    if canonical is None:
        errors.append("Package-first catalog snapshot is unavailable")
    else:
        if canonical.get("version") != "2026-08-01.3":
            errors.append(
                "Effective catalog version mismatch: expected 2026-08-01.3; "
                f"observed {canonical.get('version')}"
            )
        expected_counts = {
            "tasks": 37,
            "datasets": 30,
            "models": 75,
            "experiments": 29,
            "features": 39,
        }
        if canonical.get("counts") != expected_counts:
            errors.append(
                f"Effective catalog counts mismatch: expected {expected_counts}; "
                f"observed {canonical.get('counts')}"
            )
        required_models = {
            "exact_preparation_scheduler",
            "fefo_inventory_simulator",
            "forecast_inventory_pipeline",
        }
        observed_models = set(canonical.get("ids", {}).get("models", []))
        missing_models = sorted(required_models - observed_models)
        if missing_models:
            errors.append(
                "Extended catalog models are missing: " + ", ".join(missing_models)
            )
        missing_capabilities = sorted(
            required_models - set(canonical.get("capabilities", {}))
        )
        if missing_capabilities:
            errors.append(
                "Extended runtime capability registrations are missing: "
                + ", ".join(missing_capabilities)
            )

        for name, snapshot in successful.items():
            if snapshot != canonical:
                errors.append(
                    f"Catalog/capability snapshot differs for import scenario {name}"
                )

    compact_results = {
        name: {
            "success": value["success"],
            "returncode": value["returncode"],
            "stderr": value["stderr"],
            "snapshot": value["snapshot"],
        }
        for name, value in results.items()
    }
    return {
        "valid": not errors,
        "canonical_scenario": canonical_name,
        "scenario_count": len(SCENARIOS),
        "scenarios": compact_results,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate catalog and capability state across isolated import orders"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = validate_catalog_import_order()
    except (OSError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        print(f"Catalog import-order validation failed: {type(exc).__name__}: {exc}")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
