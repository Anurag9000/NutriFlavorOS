from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBRecipe
from backend.preparation_models import DBRecipePreparationProfile
from scripts import import_preparation_profiles as importer


def _profile(recipe_id: str, version: str, *, duration: int = 10) -> dict:
    return {
        "recipe_id": recipe_id,
        "profile_version": version,
        "schema_version": "1",
        "supported_servings_min": 1,
        "supported_servings_max": 4,
        "task_templates": [
            {
                "template_id": "heat",
                "name": "Heat",
                "duration_min_minutes": duration,
                "duration_max_minutes": duration,
                "resource_demands": {"burner": 1},
                "dependencies": [],
                "active_work": True,
                "unattended_allowed": False,
            }
        ],
        "source_name": "Manifest fixture",
        "source_url": f"https://example.test/{recipe_id}/{version}",
        "source_version": version,
        "evidence_status": "reviewed",
        "reviewed_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
        "reviewed_by": "Evidence reviewer",
        "active": True,
    }


@pytest.fixture()
def database(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        for recipe_id in ("recipe-a", "recipe-b"):
            db.add(
                DBRecipe(
                    id=recipe_id,
                    name=recipe_id,
                    description="",
                    ingredients=["water"],
                    ingredient_data=[],
                    servings=2,
                    calories=100,
                    macros={},
                    flavor_profile={},
                    tags=[],
                    instructions=[],
                    estimated_cost=1,
                    nutrition_basis="per_serving",
                )
            )
        db.commit()
    monkeypatch.setattr(importer, "SessionLocal", Session)
    return Session


def _write_input(tmp_path, profiles):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps({"profiles": profiles}, indent=2),
        encoding="utf-8",
    )
    return path


def _assert_manifest_integrity(manifest: dict):
    observed = manifest["manifest_sha256"]
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256")
    assert observed == importer._manifest_hash(unsigned)
    assert len(observed) == 64


def test_dry_run_validates_current_database_without_mutation(
    tmp_path, database
):
    input_path = _write_input(
        tmp_path,
        [_profile("recipe-a", "1"), _profile("recipe-b", "1")],
    )
    manifest_path = tmp_path / "dry-run.json"
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=False,
        operator=None,
    )

    assert code == 0
    assert manifest["status"] == "validated_dry_run"
    assert manifest["database_committed"] is False
    assert manifest["profile_count"] == 2
    assert manifest["reviewed_profile_count"] == 2
    assert manifest["reviewer_identities"] == ["Evidence reviewer"]
    assert all(row["planned_action"] == "register" for row in manifest["rows"])
    assert manifest["input_sha256"] == importer.file_sha256(input_path)
    _assert_manifest_integrity(manifest)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    with database() as db:
        assert db.query(DBRecipePreparationProfile).count() == 0


def test_apply_requires_operator_before_database_mutation(tmp_path, database):
    input_path = _write_input(tmp_path, [_profile("recipe-a", "1")])
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=tmp_path / "missing-operator.json",
        apply=True,
        operator="   ",
    )
    assert code == 2
    assert manifest["status"] == "failed"
    assert manifest["error"]["stage"] == "operator_validation"
    assert manifest["database_committed"] is False
    with database() as db:
        assert db.query(DBRecipePreparationProfile).count() == 0


def test_atomic_apply_and_idempotent_reapply_have_explicit_outcomes(
    tmp_path, database
):
    input_path = _write_input(
        tmp_path,
        [_profile("recipe-b", "1"), _profile("recipe-a", "1")],
    )
    manifest_path = tmp_path / "apply.json"
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="Release operator",
    )
    assert code == 0
    assert manifest["status"] == "applied"
    assert manifest["database_committed"] is True
    assert manifest["committed_record_count"] == 2
    assert [row["outcome"] for row in manifest["rows"]] == [
        "registered",
        "registered",
    ]
    assert all(row["record_id"] for row in manifest["rows"])
    _assert_manifest_integrity(manifest)
    with database() as db:
        assert db.query(DBRecipePreparationProfile).count() == 2

    second_code, second = importer.run_import(
        input_path=input_path,
        manifest_path=tmp_path / "reapply.json",
        apply=True,
        operator="Release operator",
    )
    assert second_code == 0
    assert second["database_committed"] is True
    assert second["committed_record_count"] == 0
    assert all(
        row["outcome"] == "idempotent_existing"
        for row in second["rows"]
    )
    with database() as db:
        assert db.query(DBRecipePreparationProfile).count() == 2


def test_contradictory_same_version_fails_without_partial_change(
    tmp_path, database
):
    original_path = _write_input(tmp_path, [_profile("recipe-a", "1")])
    code, _ = importer.run_import(
        input_path=original_path,
        manifest_path=tmp_path / "first.json",
        apply=True,
        operator="Release operator",
    )
    assert code == 0

    conflicting_path = tmp_path / "conflict.json"
    conflicting_path.write_text(
        json.dumps({"profiles": [_profile("recipe-a", "1", duration=11)]}),
        encoding="utf-8",
    )
    conflict_code, conflict = importer.run_import(
        input_path=conflicting_path,
        manifest_path=tmp_path / "conflict-manifest.json",
        apply=True,
        operator="Release operator",
    )
    assert conflict_code == 3
    assert conflict["status"] == "failed"
    assert conflict["database_committed"] is False
    assert "different evidence content" in conflict["error"]["message"]
    with database() as db:
        rows = db.query(DBRecipePreparationProfile).all()
        assert len(rows) == 1
        assert rows[0].task_templates[0]["duration_max_minutes"] == 10


def test_unknown_recipe_batch_does_not_commit_known_rows(tmp_path, database):
    input_path = _write_input(
        tmp_path,
        [_profile("recipe-a", "1"), _profile("missing", "1")],
    )
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=tmp_path / "unknown.json",
        apply=True,
        operator="Release operator",
    )
    assert code == 3
    assert manifest["database_committed"] is False
    assert "Unknown recipe_id" in manifest["error"]["message"]
    with database() as db:
        assert db.query(DBRecipePreparationProfile).count() == 0


def test_preapply_manifest_failure_aborts_without_database_commit(
    tmp_path, database, monkeypatch
):
    input_path = _write_input(tmp_path, [_profile("recipe-a", "1")])

    def fail_write(path, manifest):
        raise OSError("disk unavailable")

    monkeypatch.setattr(importer, "_write_manifest", fail_write)
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=tmp_path / "unwritable.json",
        apply=True,
        operator="Release operator",
    )
    assert code == 2
    assert manifest["status"] == "manifest_write_failed"
    assert manifest["database_committed"] is False
    with database() as db:
        assert db.query(DBRecipePreparationProfile).count() == 0


def test_postcommit_manifest_failure_is_reported_honestly(
    tmp_path, database, monkeypatch
):
    input_path = _write_input(tmp_path, [_profile("recipe-a", "1")])
    real_write = importer._write_manifest
    calls = {"count": 0}

    def fail_second_write(path, manifest):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("disk became unavailable")
        return real_write(path, manifest)

    monkeypatch.setattr(importer, "_write_manifest", fail_second_write)
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=tmp_path / "postcommit.json",
        apply=True,
        operator="Release operator",
    )
    assert code == 4
    assert manifest["status"] == "applied_manifest_write_failed"
    assert manifest["database_committed"] is True
    assert manifest["error"]["database_already_committed"] is True
    with database() as db:
        assert db.query(DBRecipePreparationProfile).count() == 1
