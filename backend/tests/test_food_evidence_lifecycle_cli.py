from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.domain.evidence_history import (
    EvidenceRecordStatus,
    IngredientConversionVersionInput,
    StoragePolicyVersionInput,
)
from backend.evidence_history_models import (
    DBEvidenceLifecycleEvent,
    DBIngredientConversionVersion,
    DBStoragePolicyVersion,
)
from backend.services.evidence_history_service import (
    register_conversion_version,
    register_storage_policy_version,
)
from scripts import manage_food_evidence_lifecycle as lifecycle_cli


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed(Session) -> tuple[int, int]:
    reviewed_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    with Session() as db:
        conversion = register_conversion_version(
            db,
            IngredientConversionVersionInput(
                canonical_name="cooked rice",
                from_unit="cup",
                to_unit="g",
                record_version="cli-v1",
                multiplier_min=120,
                multiplier_max=125,
                source_name="CLI fixture",
                source_url="https://example.test/conversion",
                source_version="cli-v1",
                evidence_status=EvidenceRecordStatus.REVIEWED,
                reviewed_at=reviewed_at,
                reviewed_by="CLI reviewer",
                active=True,
            ),
        )
        policy = register_storage_policy_version(
            db,
            StoragePolicyVersionInput(
                policy_key="rice_refrigerated",
                policy_version="cli-v1",
                food_category="cooked rice",
                storage_state="refrigerated",
                duration_min_hours=72,
                duration_max_hours=96,
                maximum_temperature_c=4,
                source_name="CLI fixture",
                source_url="https://example.test/policy",
                source_version="cli-v1",
                evidence_status=EvidenceRecordStatus.REVIEWED,
                reviewed_at=reviewed_at,
                reviewed_by="CLI reviewer",
                safety_scope="test_only",
                active=True,
            ),
        )
        return conversion.id, policy.id


def _document(conversion_id: int, policy_id: int, *, actor: str = "CLI operator") -> dict:
    return {
        "document_version": "evidence-lifecycle-v1",
        "actions": [
            {
                "target_kind": "conversion",
                "target_id": conversion_id,
                "action": "deactivated",
                "actor": actor,
                "reason": "Withdraw conversion from future automatic use",
                "idempotency_key": "cli-lifecycle-conversion-v1",
                "metadata": {"ticket": "CLI-1"},
            },
            {
                "target_kind": "storage_policy",
                "target_id": policy_id,
                "action": "rejected",
                "actor": actor,
                "reason": "Reject policy after evidence review",
                "idempotency_key": "cli-lifecycle-policy-v1",
                "metadata": {"ticket": "CLI-2"},
            },
        ],
    }


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _assert_manifest_hash(manifest: dict) -> None:
    assert len(manifest["manifest_sha256"]) == 64
    assert manifest["manifest_sha256"] == lifecycle_cli._manifest_hash(manifest)


def test_dry_run_records_exact_targets_without_mutation(tmp_path, monkeypatch):
    Session = _session_factory()
    conversion_id, policy_id = _seed(Session)
    monkeypatch.setattr(lifecycle_cli, "SessionLocal", Session)
    input_path = tmp_path / "lifecycle.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document(conversion_id, policy_id))

    code, manifest = lifecycle_cli.run_lifecycle(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=False,
        operator=None,
    )
    assert code == 0
    assert manifest["status"] == "validated_dry_run"
    assert manifest["database_committed"] is False
    assert manifest["action_count"] == 2
    assert {value["planned_action"] for value in manifest["rows"]} == {
        "deactivate_active_target"
    }
    assert {value["target_content_hash"] for value in manifest["rows"]}
    _assert_manifest_hash(manifest)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    with Session() as db:
        assert db.get(DBIngredientConversionVersion, conversion_id).active is True
        assert db.get(DBStoragePolicyVersion, policy_id).active is True
        assert db.query(DBEvidenceLifecycleEvent).count() == 0


def test_apply_and_idempotent_reapply_are_manifested(tmp_path, monkeypatch):
    Session = _session_factory()
    conversion_id, policy_id = _seed(Session)
    monkeypatch.setattr(lifecycle_cli, "SessionLocal", Session)
    input_path = tmp_path / "lifecycle.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document(conversion_id, policy_id))

    code, applied = lifecycle_cli.run_lifecycle(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="CLI operator",
    )
    assert code == 0
    assert applied["status"] == "applied"
    assert applied["database_committed"] is True
    assert applied["changed_target_count"] == 2
    assert applied["already_inactive_count"] == 0
    assert applied["idempotent_count"] == 0
    assert {value["outcome"] for value in applied["rows"]} == {"recorded"}
    assert all(value["event_id"] for value in applied["rows"])
    _assert_manifest_hash(applied)

    code, retry = lifecycle_cli.run_lifecycle(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="CLI operator",
    )
    assert code == 0
    assert retry["database_committed"] is True
    assert retry["changed_target_count"] == 0
    assert retry["idempotent_count"] == 2
    assert {value["outcome"] for value in retry["rows"]} == {
        "idempotent_existing"
    }
    with Session() as db:
        assert db.get(DBIngredientConversionVersion, conversion_id).active is False
        assert db.get(DBStoragePolicyVersion, policy_id).active is False
        assert db.query(DBEvidenceLifecycleEvent).count() == 2


def test_apply_requires_matching_operator_and_actors(tmp_path, monkeypatch):
    Session = _session_factory()
    conversion_id, policy_id = _seed(Session)
    monkeypatch.setattr(lifecycle_cli, "SessionLocal", Session)
    input_path = tmp_path / "lifecycle.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document(conversion_id, policy_id, actor="Document actor"))

    code, manifest = lifecycle_cli.run_lifecycle(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="Different operator",
    )
    assert code == 2
    assert manifest["status"] == "failed"
    assert manifest["error"]["stage"] == "actor_validation"
    assert manifest["database_committed"] is False
    with Session() as db:
        assert db.get(DBIngredientConversionVersion, conversion_id).active is True
        assert db.get(DBStoragePolicyVersion, policy_id).active is True
        assert db.query(DBEvidenceLifecycleEvent).count() == 0


def test_unknown_target_rolls_back_complete_cli_batch(tmp_path, monkeypatch):
    Session = _session_factory()
    conversion_id, policy_id = _seed(Session)
    monkeypatch.setattr(lifecycle_cli, "SessionLocal", Session)
    value = _document(conversion_id, policy_id)
    value["actions"][1]["target_id"] = 999999
    input_path = tmp_path / "lifecycle.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, value)

    code, manifest = lifecycle_cli.run_lifecycle(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="CLI operator",
    )
    assert code == 3
    assert manifest["status"] == "failed"
    assert manifest["database_committed"] is False
    assert manifest["error"]["stage"] == "database_preflight_or_atomic_apply"
    with Session() as db:
        assert db.get(DBIngredientConversionVersion, conversion_id).active is True
        assert db.get(DBStoragePolicyVersion, policy_id).active is True
        assert db.query(DBEvidenceLifecycleEvent).count() == 0


def test_manifest_failure_before_apply_prevents_mutation(tmp_path, monkeypatch):
    Session = _session_factory()
    conversion_id, policy_id = _seed(Session)
    monkeypatch.setattr(lifecycle_cli, "SessionLocal", Session)
    input_path = tmp_path / "lifecycle.json"
    _write(input_path, _document(conversion_id, policy_id))

    def fail_write(_path: Path, _manifest: dict) -> None:
        raise OSError("manifest filesystem unavailable")

    monkeypatch.setattr(lifecycle_cli, "_write_manifest", fail_write)
    code, manifest = lifecycle_cli.run_lifecycle(
        input_path=input_path,
        manifest_path=tmp_path / "manifest.json",
        apply=True,
        operator="CLI operator",
    )
    assert code == 2
    assert manifest["status"] == "manifest_write_failed"
    assert manifest["database_committed"] is False
    with Session() as db:
        assert db.get(DBIngredientConversionVersion, conversion_id).active is True
        assert db.get(DBStoragePolicyVersion, policy_id).active is True
        assert db.query(DBEvidenceLifecycleEvent).count() == 0


def test_final_manifest_failure_reports_committed_lifecycle(tmp_path, monkeypatch):
    Session = _session_factory()
    conversion_id, policy_id = _seed(Session)
    monkeypatch.setattr(lifecycle_cli, "SessionLocal", Session)
    input_path = tmp_path / "lifecycle.json"
    manifest_path = tmp_path / "manifest.json"
    _write(input_path, _document(conversion_id, policy_id))
    real_write = lifecycle_cli._write_manifest
    calls = 0

    def fail_second_write(path: Path, manifest: dict) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("final manifest replacement failed")
        real_write(path, manifest)

    monkeypatch.setattr(lifecycle_cli, "_write_manifest", fail_second_write)
    code, manifest = lifecycle_cli.run_lifecycle(
        input_path=input_path,
        manifest_path=manifest_path,
        apply=True,
        operator="CLI operator",
    )
    assert code == 4
    assert manifest["status"] == "applied_manifest_write_failed"
    assert manifest["database_committed"] is True
    assert manifest["error"]["database_already_committed"] is True
    with Session() as db:
        assert db.get(DBIngredientConversionVersion, conversion_id).active is False
        assert db.get(DBStoragePolicyVersion, policy_id).active is False
        assert db.query(DBEvidenceLifecycleEvent).count() == 2
