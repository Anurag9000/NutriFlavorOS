#!/usr/bin/env python3
"""Validate cross-file contracts that must evolve together.

This validator intentionally checks declarations, not model quality. It catches
catalog/capability drift, stale migration heads, missing benchmark fixtures,
missing release contracts, migration-chain defects, import-order drift, and
stale public catalog declarations.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from backend.domain.evidence_import import FoodEvidenceImportDocument
from backend.domain.evidence_lifecycle import EvidenceLifecycleBatchDocument
from backend.research.capabilities import (
    assert_core_capabilities_valid,
    implementation_status,
)
from backend.research.catalog import Readiness, get_catalog
from backend.schema_verification import (
    CURRENT_ALEMBIC_REVISION,
    CURRENT_REQUIRED_TABLES,
)
from scripts.validate_alembic_chain import validate_alembic_chain
from scripts.validate_catalog_import_order import validate_catalog_import_order


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BENCHMARK_FILES = {
    "planner": ROOT / "benchmarks" / "planner_small.json",
    "preparation_scheduler": ROOT
    / "benchmarks"
    / "preparation_scheduler_small.json",
    "inventory": ROOT / "benchmarks" / "inventory_small.json",
    "forecast_inventory": ROOT / "benchmarks" / "forecast_inventory_small.json",
}
EXPECTED_TYPED_FIXTURES = {
    "food_evidence_import": ROOT
    / "benchmarks"
    / "food_evidence_import_small.json",
    "food_evidence_lifecycle": ROOT
    / "benchmarks"
    / "food_evidence_lifecycle_small.json",
}
EXPECTED_CONTRACT_FILES = {
    "openapi": ROOT / "contracts" / "openapi_required.json",
    "frontend_openapi_bindings": ROOT
    / "contracts"
    / "frontend_openapi_bindings.json",
    "preparation_operations_frontend_bindings": ROOT
    / "contracts"
    / "preparation_operations_frontend_bindings.json",
}
DOCUMENTS_WITH_CATALOG_COUNTS = {
    ROOT / "README.md",
    ROOT / "docs" / "RESEARCH_PLATFORM.md",
    ROOT / "docs" / "IMPLEMENTATION_STATUS.md",
}
EXPECTED_EVIDENCE_TABLES = {
    "ingredient_conversion_versions",
    "storage_policy_versions",
    "leftover_storage_policy_evidence",
    "evidence_lifecycle_events",
}
EXPECTED_PREPARATION_OPERATIONS_TABLES = {
    "resource_calendar_versions",
    "household_preparation_resources",
    "persisted_preparation_schedules",
    "preparation_schedule_events",
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


def _json_object(path: Path, *, label: str, errors: list[str]) -> dict | None:
    if not path.is_file():
        errors.append(f"missing {label}: {path.relative_to(ROOT)}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object: {path.relative_to(ROOT)}")
        return None
    return value


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

    missing_schema_contract = EXPECTED_EVIDENCE_TABLES - set(CURRENT_REQUIRED_TABLES)
    if missing_schema_contract:
        errors.append(
            "immutable evidence tables missing from runtime schema contract: "
            + ", ".join(sorted(missing_schema_contract))
        )
    missing_preparation_tables = (
        EXPECTED_PREPARATION_OPERATIONS_TABLES - set(CURRENT_REQUIRED_TABLES)
    )
    if missing_preparation_tables:
        errors.append(
            "preparation operations tables missing from runtime schema contract: "
            + ", ".join(sorted(missing_preparation_tables))
        )

    for label, path in sorted(EXPECTED_BENCHMARK_FILES.items()):
        _json_object(path, label=f"{label} benchmark fixture", errors=errors)

    typed_fixture_report: dict[str, str] = {}
    for label, path in sorted(EXPECTED_TYPED_FIXTURES.items()):
        value = _json_object(path, label=f"{label} typed fixture", errors=errors)
        if value is not None:
            try:
                if label == "food_evidence_import":
                    document = FoodEvidenceImportDocument.model_validate(value)
                elif label == "food_evidence_lifecycle":
                    document = EvidenceLifecycleBatchDocument.model_validate(value)
                else:  # pragma: no cover - guarded by the constant above
                    raise ValueError(f"Unknown typed fixture label: {label}")
                typed_fixture_report[label] = document.document_version
            except (TypeError, ValueError) as exc:
                errors.append(
                    f"typed fixture validation failed for {path.relative_to(ROOT)}: {exc}"
                )

    contract_report: dict[str, str] = {}
    for label, path in sorted(EXPECTED_CONTRACT_FILES.items()):
        value = _json_object(path, label=f"{label} release contract", errors=errors)
        if value is not None:
            version = value.get("contract_version")
            if not isinstance(version, str) or not version:
                errors.append(
                    f"release contract has no contract_version: {path.relative_to(ROOT)}"
                )
            else:
                contract_report[label] = version

    for path in sorted(DOCUMENTS_WITH_CATALOG_COUNTS):
        errors.extend(_document_errors(path, counts, catalog.version))

    migration_matches = sorted(
        (ROOT / "backend" / "migrations" / "versions").glob(
            f"{CURRENT_ALEMBIC_REVISION}_*.py"
        )
    )
    if len(migration_matches) != 1:
        rendered = ", ".join(
            str(path.relative_to(ROOT)) for path in migration_matches
        ) or "none"
        errors.append(
            "schema verifier head must map to exactly one migration file; "
            f"observed {rendered}"
        )

    alembic_report = validate_alembic_chain()
    errors.extend(
        f"Alembic chain: {value}" for value in alembic_report["errors"]
    )

    import_order_report = validate_catalog_import_order()
    errors.extend(
        f"Catalog import order: {value}"
        for value in import_order_report["errors"]
    )
    successful_import_scenarios = sorted(
        name
        for name, value in import_order_report["scenarios"].items()
        if value["success"]
    )

    return {
        "valid": not errors,
        "catalog_version": catalog.version,
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "counts": counts,
        "capability_count": len(capabilities),
        "required_runtime_tables": sorted(CURRENT_REQUIRED_TABLES),
        "benchmark_fixtures": {
            label: str(path.relative_to(ROOT))
            for label, path in sorted(EXPECTED_BENCHMARK_FILES.items())
        },
        "typed_fixtures": typed_fixture_report,
        "release_contracts": contract_report,
        "migration_files": [
            str(path.relative_to(ROOT)) for path in migration_matches
        ],
        "alembic_chain": {
            "valid": alembic_report["valid"],
            "heads": alembic_report["heads"],
            "bases": alembic_report["bases"],
            "revision_count": alembic_report["revision_count"],
            "migration_file_count": alembic_report["migration_file_count"],
            "linear_chain": alembic_report["linear_chain"],
        },
        "catalog_import_order": {
            "valid": import_order_report["valid"],
            "canonical_scenario": import_order_report["canonical_scenario"],
            "scenario_count": import_order_report["scenario_count"],
            "successful_scenarios": successful_import_scenarios,
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
