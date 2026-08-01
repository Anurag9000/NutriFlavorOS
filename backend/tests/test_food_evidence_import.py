from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.evidence_history_models import (
    DBIngredientConversionVersion,
    DBStoragePolicyVersion,
)
from scripts import import_food_evidence as importer


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _document(*, multiplier: float = 120, policy_version: str = "policy-v1") -> dict:
    reviewed_at = datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat()
    return {
        "document_version": "food-evidence-import-v1",
        "conversion_versions": [
            {
                "canonical_name": "cooked rice",
                "from_unit": "cup",
                "to_unit": "g",
                "record_version": "conversion-v1",
                "multiplier_min": multiplier,
                "multiplier_max": multiplier,
                "source_name": "Import fixture",
                "source_url": "https://example.test/conversion",
                "source_version": "source-v1",
                "evidence_status": "reviewed",
                "reviewed_at": reviewed_at,
                "reviewed_by": "Import reviewer",
                "active": True,
            }
        ],
        "storage_policy_versions": [
            {
                "policy_key": "rice_refrigerated",
                "policy_version": policy_version,
                "food_category": "cooked rice",
                "storage_state": "refrigerated",
                "duration_min_hours": 72,
                "duration_max_hours": 96,
                "maximum_temperature_c": 4,
                "source_name": "Import fixture",
                "source_url": "https://example.test/policy",
                "source_version": "source-v1",
                "evidence_status": "reviewed",
                "reviewed_at": reviewed_at,
                "reviewed_by": "Import reviewer",
                "safety_scope": "test_only",
                "active": True,
            }
        ],
    }


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _assert_manifest_hash(manifest: dict) -> None:
    assert len(manifest["manifest_sha256"]) == 64
    assert manifest["manifest_sha256"] == importer._manifest_hash(manifest)


def test_dry_run_writes_manifest_without_database_mutation(tmp_path, monkeypatch):
    Session = _session_factory()
    monkeypatch.setattr(importer, "SessionLocal", Session)
    input_path = tmp_path / "evidence.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document())

    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=False,
        operator=None,
    )
    assert code == 0
    assert manifest["status"] == "validated_dry_run"
    assert manifest["database_committed"] is False
    assert manifest["conversion_count"] == 1
    assert manifest["storage_policy_count"] == 1
    assert manifest["reviewer_identities"] == ["Import reviewer"]
    assert {row["planned_action"] for row in manifest["rows"]} == {
        "register_active_reviewed"
    }
    _assert_manifest_hash(manifest)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    with Session() as db:
        assert db.query(DBIngredientConversionVersion).count() == 0
        assert db.query(DBStoragePolicyVersion).count() == 0


def test_apply_and_idempotent_reapply_are_manifested(tmp_path, monkeypatch):
    Session = _session_factory()
    monkeypatch.setattr(importer, "SessionLocal", Session)
    input_path = tmp_path / "evidence.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document())

    code, applied = importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="operator@example.test",
    )
    assert code == 0
    assert applied["status"] == "applied"
    assert applied["database_committed"] is True
    assert applied["inserted_count"] == 2
    assert applied["idempotent_count"] == 0
    assert {row["outcome"] for row in applied["rows"]} == {"registered"}
    assert all(row["record_id"] for row in applied["rows"])
    _assert_manifest_hash(applied)

    code, retry = importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="operator@example.test",
    )
    assert code == 0
    assert retry["inserted_count"] == 0
    assert retry["idempotent_count"] == 2
    assert {row["outcome"] for row in retry["rows"]} == {
        "idempotent_existing"
    }
    with Session() as db:
        assert db.query(DBIngredientConversionVersion).count() == 1
        assert db.query(DBStoragePolicyVersion).count() == 1


def test_apply_requires_operator_and_never_mutates(tmp_path, monkeypatch):
    Session = _session_factory()
    monkeypatch.setattr(importer, "SessionLocal", Session)
    input_path = tmp_path / "evidence.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document())

    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator=None,
    )
    assert code == 2
    assert manifest["error"]["stage"] == "operator_validation"
    assert manifest["database_committed"] is False
    with Session() as db:
        assert db.query(DBIngredientConversionVersion).count() == 0
        assert db.query(DBStoragePolicyVersion).count() == 0


def test_contradictory_version_prevents_new_policy_from_committing(tmp_path, monkeypatch):
    Session = _session_factory()
    monkeypatch.setattr(importer, "SessionLocal", Session)
    input_path = tmp_path / "evidence.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document())
    assert importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="operator@example.test",
    )[0] == 0

    _write(input_path, _document(multiplier=121, policy_version="policy-v2"))
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="operator@example.test",
    )
    assert code == 3
    assert manifest["status"] == "failed"
    assert manifest["database_committed"] is False
    assert manifest["error"]["stage"] == "database_preflight_or_atomic_apply"
    with Session() as db:
        assert db.query(DBIngredientConversionVersion).count() == 1
        assert (
            db.query(DBStoragePolicyVersion)
            .filter(DBStoragePolicyVersion.policy_version == "policy-v2")
            .count()
            == 0
        )


def test_manifest_failure_before_apply_prevents_database_commit(tmp_path, monkeypatch):
    Session = _session_factory()
    monkeypatch.setattr(importer, "SessionLocal", Session)
    input_path = tmp_path / "evidence.json"
    _write(input_path, _document())

    def fail_write(_path: Path, _manifest: dict) -> None:
        raise OSError("manifest filesystem unavailable")

    monkeypatch.setattr(importer, "_write_manifest", fail_write)
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=tmp_path / "manifest.json",
        apply=True,
        operator="operator@example.test",
    )
    assert code == 2
    assert manifest["status"] == "manifest_write_failed"
    assert manifest["database_committed"] is False
    with Session() as db:
        assert db.query(DBIngredientConversionVersion).count() == 0
        assert db.query(DBStoragePolicyVersion).count() == 0


def test_final_manifest_failure_reports_already_committed_state(tmp_path, monkeypatch):
    Session = _session_factory()
    monkeypatch.setattr(importer, "SessionLocal", Session)
    input_path = tmp_path / "evidence.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document())
    real_write = importer._write_manifest
    calls = 0

    def fail_second_write(path: Path, manifest: dict) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("final manifest replacement failed")
        real_write(path, manifest)

    monkeypatch.setattr(importer, "_write_manifest", fail_second_write)
    code, manifest = importer.run_import(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="operator@example.test",
    )
    assert code == 4
    assert manifest["status"] == "applied_manifest_write_failed"
    assert manifest["database_committed"] is True
    assert manifest["error"]["database_already_committed"] is True
    with Session() as db:
        assert db.query(DBIngredientConversionVersion).count() == 1
        assert db.query(DBStoragePolicyVersion).count() == 1
