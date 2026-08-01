from __future__ import annotations

import json

from scripts.validate_catalog_import_order import (
    MARKER,
    SCENARIOS,
    _snapshot_program,
    validate_catalog_import_order,
)


def test_generated_snapshot_program_is_valid_python():
    program = _snapshot_program(SCENARIOS["mixed_reimports"])
    compile(program, "<catalog-import-order>", "exec")
    assert "import json" in program
    assert MARKER in program
    assert "implementation_status" in program


def test_catalog_and_capability_state_is_import_order_invariant():
    report = validate_catalog_import_order()
    assert report["canonical_scenario"] == "package_first"
    assert report["scenario_count"] == len(SCENARIOS) == 6
    assert set(report["scenarios"]) == set(SCENARIOS)
    assert all(value["success"] for value in report["scenarios"].values())

    snapshots = [
        json.dumps(value["snapshot"], sort_keys=True)
        for value in report["scenarios"].values()
    ]
    assert len(set(snapshots)) == 1
    canonical = report["scenarios"]["package_first"]["snapshot"]
    assert canonical["version"] == "2026-08-01.3"
    assert canonical["counts"] == {
        "tasks": 37,
        "datasets": 30,
        "models": 75,
        "experiments": 29,
        "features": 39,
    }
    assert {
        "exact_preparation_scheduler",
        "fefo_inventory_simulator",
        "forecast_inventory_pipeline",
    } <= set(canonical["capabilities"])
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
