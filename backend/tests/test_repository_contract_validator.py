from __future__ import annotations

from scripts.validate_repository_contracts import validate_repository_contracts


def test_repository_contracts_are_synchronized():
    report = validate_repository_contracts()
    assert report["catalog_version"] == "2026-08-01.3"
    assert report["migration_head"] == "20260801_0008"
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
        "evidence_lifecycle_events",
    } <= set(report["required_runtime_tables"])
    assert report["typed_fixtures"] == {
        "food_evidence_import": "food-evidence-import-v1",
        "food_evidence_lifecycle": "evidence-lifecycle-v1",
    }
    assert report["release_contracts"] == {
        "frontend_openapi_bindings": "2026-08-01.2",
        "openapi": "2026-08-01.3",
    }
    assert report["migration_files"] == [
        "backend/migrations/versions/20260801_0008_evidence_lifecycle.py"
    ]
    assert report["alembic_chain"]["valid"] is True
    assert report["alembic_chain"]["heads"] == ["20260801_0008"]
    assert len(report["alembic_chain"]["bases"]) == 1
    assert report["alembic_chain"]["linear_chain"][-1] == "20260801_0008"
    assert (
        report["alembic_chain"]["revision_count"]
        == report["alembic_chain"]["migration_file_count"]
    )
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
