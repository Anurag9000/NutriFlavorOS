from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.domain.evidence_history import (
    EvidenceRecordStatus,
    IngredientConversionVersionInput,
    StoragePolicyVersionInput,
)
from backend.domain.evidence_lifecycle import (
    EvidenceLifecycleAction,
    EvidenceLifecycleBatchDocument,
    EvidenceLifecycleRequest,
    EvidenceTargetKind,
)
from backend.evidence_history_models import (
    DBIngredientConversionVersion,
    DBStoragePolicyVersion,
)
from backend.services.evidence_history_service import register_conversion_version
from backend.services.evidence_import_service import (
    preflight_food_evidence,
    register_food_evidence_atomic,
)
from backend.services.evidence_lifecycle_service import (
    apply_evidence_lifecycle_batch,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _conversion(
    version: str,
    *,
    multiplier: float = 120.0,
    active: bool = True,
) -> IngredientConversionVersionInput:
    return IngredientConversionVersionInput(
        canonical_name="cooked rice",
        from_unit="cup",
        to_unit="g",
        record_version=version,
        multiplier_min=multiplier,
        multiplier_max=multiplier,
        source_name="Batch fixture",
        source_url=f"https://example.test/conversion/{version}",
        source_version=version,
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        reviewed_by="Batch reviewer",
        active=active,
    )


def _policy(
    version: str,
    *,
    duration: float = 96.0,
    active: bool = True,
) -> StoragePolicyVersionInput:
    return StoragePolicyVersionInput(
        policy_key="rice_refrigerated",
        policy_version=version,
        food_category="cooked rice",
        storage_state="refrigerated",
        duration_min_hours=72,
        duration_max_hours=duration,
        maximum_temperature_c=4,
        source_name="Batch fixture",
        source_url=f"https://example.test/policy/{version}",
        source_version=version,
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        reviewed_by="Batch reviewer",
        safety_scope="test_only",
        active=active,
    )


def test_joint_batch_preflight_apply_and_idempotent_reapply(db):
    previews = preflight_food_evidence(db, [_conversion("v1")], [_policy("v1")])
    assert [value.planned_action for value in previews] == [
        "register_active_reviewed",
        "register_active_reviewed",
    ]

    result = register_food_evidence_atomic(
        db,
        [_conversion("v1")],
        [_policy("v1")],
    )
    assert result.inserted_count == 2
    assert result.idempotent_count == 0
    assert result.conversions[0].active is True
    assert result.storage_policies[0].active is True

    retry = register_food_evidence_atomic(
        db,
        [_conversion("v1")],
        [_policy("v1")],
    )
    assert retry.inserted_count == 0
    assert retry.idempotent_count == 2
    assert retry.conversions[0].id == result.conversions[0].id
    assert retry.storage_policies[0].id == result.storage_policies[0].id


def test_successor_batch_forms_exact_supersession_chains(db):
    first = register_food_evidence_atomic(
        db,
        [_conversion("v1")],
        [_policy("v1")],
    )
    second = register_food_evidence_atomic(
        db,
        [_conversion("v2", multiplier=118)],
        [_policy("v2", duration=72)],
    )
    assert second.conversions[0].supersedes_conversion_id == first.conversions[0].id
    assert second.storage_policies[0].supersedes_policy_id == first.storage_policies[0].id
    assert db.get(DBIngredientConversionVersion, first.conversions[0].id).active is False
    assert db.get(DBStoragePolicyVersion, first.storage_policies[0].id).active is False
    assert second.conversions[0].active is True
    assert second.storage_policies[0].active is True


def test_contradictory_existing_version_prevents_all_batch_writes(db):
    existing = register_conversion_version(db, _conversion("v1"))
    contradictory = _conversion("v1", multiplier=121)
    with pytest.raises(ValueError, match="different evidence content"):
        register_food_evidence_atomic(
            db,
            [contradictory],
            [_policy("new-policy")],
        )
    assert db.get(DBIngredientConversionVersion, existing.id) is not None
    assert (
        db.query(DBStoragePolicyVersion)
        .filter(DBStoragePolicyVersion.policy_version == "new-policy")
        .count()
        == 0
    )


def test_batch_rejects_ambiguous_active_reviewed_successors(db):
    with pytest.raises(ValueError, match="at most one active reviewed conversion"):
        register_food_evidence_atomic(
            db,
            [_conversion("v1"), _conversion("v2", multiplier=118)],
            [],
        )
    with pytest.raises(ValueError, match="at most one active reviewed storage-policy"):
        register_food_evidence_atomic(
            db,
            [],
            [_policy("v1"), _policy("v2", duration=72)],
        )


def test_inactive_reviewed_history_can_be_imported_without_superseding(db):
    active = register_food_evidence_atomic(db, [_conversion("active")], [_policy("active")])
    historical = register_food_evidence_atomic(
        db,
        [_conversion("historical", multiplier=110, active=False)],
        [_policy("historical", duration=48, active=False)],
    )
    assert historical.conversions[0].active is False
    assert historical.storage_policies[0].active is False
    assert db.get(DBIngredientConversionVersion, active.conversions[0].id).active is True
    assert db.get(DBStoragePolicyVersion, active.storage_policies[0].id).active is True


def test_active_batch_successor_links_to_latest_reviewed_inactive_predecessor(db):
    first = register_food_evidence_atomic(
        db,
        [_conversion("v1")],
        [_policy("v1")],
    )
    lifecycle = EvidenceLifecycleBatchDocument(
        actions=[
            EvidenceLifecycleRequest(
                target_kind=EvidenceTargetKind.CONVERSION,
                target_id=first.conversions[0].id,
                action=EvidenceLifecycleAction.REJECTED,
                actor="Batch reviewer",
                reason="Withdraw conversion before corrected replacement",
                idempotency_key="batch-lineage-conversion-v1",
            ),
            EvidenceLifecycleRequest(
                target_kind=EvidenceTargetKind.STORAGE_POLICY,
                target_id=first.storage_policies[0].id,
                action=EvidenceLifecycleAction.DEACTIVATED,
                actor="Batch reviewer",
                reason="Withdraw policy before corrected replacement",
                idempotency_key="batch-lineage-policy-v1",
            ),
        ]
    )
    apply_evidence_lifecycle_batch(db, lifecycle)

    previews = preflight_food_evidence(
        db,
        [_conversion("v2", multiplier=118)],
        [_policy("v2", duration=72)],
    )
    assert [value.planned_action for value in previews] == [
        "register_and_supersede",
        "register_and_supersede",
    ]
    assert previews[0].supersedes_record_id == first.conversions[0].id
    assert previews[1].supersedes_record_id == first.storage_policies[0].id

    second = register_food_evidence_atomic(
        db,
        [_conversion("v2", multiplier=118)],
        [_policy("v2", duration=72)],
    )
    assert second.conversions[0].supersedes_conversion_id == first.conversions[0].id
    assert second.storage_policies[0].supersedes_policy_id == first.storage_policies[0].id
    assert second.conversions[0].active is True
    assert second.storage_policies[0].active is True
