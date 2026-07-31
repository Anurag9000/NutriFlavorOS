#!/usr/bin/env python3
"""Validate cross-file contracts that must evolve together.

This validator intentionally checks declarations, not model quality. It catches
catalog/capability drift, stale migration heads, missing benchmark fixtures, and
stale catalog counts in public documentation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

from backend.research.capabilities import (
    assert_core_capabilities_valid,
    implementation_status,
)
from backend.research.catalog import Readiness, get_catalog
from backend.schema_verification import CURRENT_ALEMBIC_REVISION


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BENCHMARK_FILES = {
    "planner": ROOT / "benchmarks" / "planner_small.json",
    "inventory": ROOT / "benchmarks" / "inventory_small.json",
    "forecast_inventory": ROOT / "benchmarks" / "forecast_inventory_small.json",
}
DOCUMENTS_WITH_CATALOG_COUNTS = {
    ROOT / "README.md",
    ROOT / "docs" / "RESEARCH_PLATFORM.md",
    ROOT / "docs" / "IMPLEMENTATION_STATUS.md",
}


def _document_errors(path: Path, expected: dict[str, int], version: str) -> list[str]:
    if not path.is_file():
        return [f"missing documentation file: {path.relative_to(ROOT)}"]
    text = path.read_text(encoding="utf-8")
    errors = []
    if version not in text:
        errors.append(
            f"{path.relative_to(ROOT)} does not declare catalog version {version}"
        )
    labels = {
        "tasks": "task",
        "datasets": "dataset",
        "models": "model",
        "experiments": "experiment",
        "features": "feature",
    }
    for collection, singular in labels.items():
        count = expected[collection]
        pattern = re.compile(
            rf"\b{count}\b[^\n]{{0,80}}\b{singular}(?:s|/algorithm families| contracts)?\b",
            re.IGNORECASE,
        )
        reverse = re.compile(
            rf"\b{singular}(?:s|/algorithm families| contracts)?\b[^\n]{{0,80}}\b{count}\b",
            re.IGNORECASE,
        )
        if not pattern.search(text) and not reverse.search(text):
            errors.append(
                f"{path.relative_to(ROOT)} does not declare {count} {collection}"
            )
    if CURRENT_ALEMBIC_REVISION not in text:
        errors.append(
            f"{path.relative_to(ROOT)} does not declare migration head {CURRENT_ALEMBIC_REVISION}"
        )
    return errors


def validate_repository_contracts() -> dict:
    catalog = get_catalog()
    summary = catalog.summary()
    counts = {
        name: int(summary[name]["total"])
        for name in ("tasks", "datasets", "models", "experiments", "features")
    }
    errors: list[str] = []

    try:
        assert_core_capabilities_valid()
    except RuntimeError as exc:
        errors.append(str(exc))

    capabilities = implementation_status()
    catalog_models = {value.id: value for value in catalog.models}
    missing_catalog = sorted(set(capabilities) - set(catalog_models))
    if missing_catalog:
        errors.append(
            "runtime capabilities missing catalog models: "
            + ", ".join(missing_catalog)
        )
    missing_capabilities = sorted(
        value.id
        for value in catalog.models
        if value.readiness in {
            Readiness.IMPLEMENTED,
            Readiness.BASELINE_AVAILABLE,
        }
        and value.id not in capabilities
    )
    if missing_capabilities:
        errors.append(
            "implemented/baseline catalog models missing runtime registrations: "
            + ", ".join(missing_capabilities)
        )

    for label, path in sorted(EXPECTED_BENCHMARK_FILES.items()):
        if not path.is_file():
            errors.append(f"missing {label} benchmark fixture: {path.relative_to(ROOT)}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")

    for path in sorted(DOCUMENTS_WITH_CATALOG_COUNTS):
        errors.extend(_document_errors(path, counts, catalog.version))

    migration_path = (
        ROOT
        / "backend"
        / "migrations"
        / "versions"
        / f"{CURRENT_ALEMBIC_REVISION}_version_preparation_profiles.py"
    )
    if not migration_path.is_file():
        errors.append(
            "schema verifier head does not map to the expected migration file: "
            + str(migration_path.relative_to(ROOT))
        )

    return {
        "valid": not errors,
        "catalog_version": catalog.version,
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "counts": counts,
        "capability_count": len(capabilities),
        "benchmark_fixtures": {
            label: str(path.relative_to(ROOT))
            for label, path in sorted(EXPECTED_BENCHMARK_FILES.items())
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate synchronized repository contracts"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_repository_contracts()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
