from __future__ import annotations

from scripts.validate_alembic_chain import validate_alembic_chain


def test_complete_alembic_history_is_one_linear_chain():
    report = validate_alembic_chain()
    assert report["expected_head"] == "20260801_0011"
    assert report["heads"] == ["20260801_0011"]
    assert len(report["bases"]) == 1
    assert report["linear_chain"][0] == report["bases"][0]
    assert report["linear_chain"][-1] == "20260801_0011"
    assert report["revision_count"] == report["migration_file_count"]
    assert len(report["linear_chain"]) == report["revision_count"]
    assert report["forks"] == {}
    assert report["orphan_files"] == []
    assert report["missing_files"] == []
    assert report["filename_mismatches"] == []
    assert all(len(value["down_revisions"]) <= 1 for value in report["edges"])
    assert all(value["dependencies"] == [] for value in report["edges"])
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
