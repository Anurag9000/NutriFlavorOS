from __future__ import annotations

from scripts.validate_repository_contracts import validate_repository_contracts


def test_repository_contracts_are_synchronized():
    report = validate_repository_contracts()
    assert report["catalog_version"] == "2026-08-01.3"
    assert report["migration_head"] == "20260801_0007"
    assert report["counts"] == {
        "tasks": 37,
        "datasets": 30,
        "models": 75,
        "experiments": 29,
        "features": 39,
    }
    assert {
        "ingredient_conversion_versions",
        "storage_policy_versions",
        "leftover_storage_policy_evidence",
    } <= set(report["required_runtime_tables"])
    assert report["migration_files"] == [
        "backend/migrations/versions/20260801_0007_version_food_evidence.py"
    ]
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
