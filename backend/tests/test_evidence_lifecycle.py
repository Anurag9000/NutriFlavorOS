from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBRecipe, DBUser
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
from backend.domain.inventory import LeftoverCreate
from backend.evidence_history_models import (
    DBEvidenceLifecycleEvent,
    DBIngredientConversionVersion,
    DBStoragePolicyVersion,
)
from backend.services.evidence_history_service import (
    active_reviewed_storage_policy,
    register_conversion_version,
    register_storage_policy_version,
    storage_policy_for_leftover,
)
from backend.services.evidence_lifecycle_preflight import (
    preflight_evidence_lifecycle_batch,
)
from backend.services.evidence_lifecycle_service import (
    apply_evidence_lifecycle_batch,
    list_evidence_lifecycle_events,
)
from backend.services.inventory_service_v4 import create_leftover


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


def _conversion(version: str, multiplier: float = 120):
    return IngredientConversionVersionInput(
        canonical_name="cooked rice",
        from_unit="cup",
        to_unit="g",
        record_version=version,
        multiplier_min=multiplier,
        multiplier_max=multiplier,
        source_name="Lifecycle fixture",
        source_url=f"https://example.test/conversion/{version}",
        source_version=version,
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        reviewed_by="Lifecycle reviewer",
        active=True,
    )


def _policy(version: str, hours: float = 96):
    return StoragePolicyVersionInput(
        policy_key="rice_refrigerated",
        policy_version=version,
        food_category="cooked rice",
        storage_state="refrigerated",
        duration_min_hours=72,
        duration_max_hours=hours,
        maximum_temperature_c=4,
        source_name="Lifecycle fixture",
        source_url=f"https://example.test/policy/{version}",
        source_version=version,
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        reviewed_by="Lifecycle reviewer",
        safety_scope="test_only",
        active=True,
    )


def _action(kind: EvidenceTargetKind, target_id: int, key: str, *, action=EvidenceLifecycleAction.DEACTIVATED):
    return EvidenceLifecycleRequest(
        target_kind=kind,
        target_id=target_id,
        action=action,
        actor="Lifecycle operator",
        reason="Reviewed evidence is being withdrawn from future automatic use",
        idempotency_key=key,
        metadata={"ticket": "EVIDENCE-42"},
    )


def test_lifecycle_batch_is_atomic_append_only_and_idempotent(db):
    conversion = register_conversion_version(db, _conversion("v1"))
    policy = register_storage_policy_version(db, _policy("v1"))
    conversion_hash = conversion.content_hash
    policy_hash = policy.content_hash
    document = EvidenceLifecycleBatchDocument(
        actions=[
            _action(EvidenceTargetKind.CONVERSION, conversion.id, "lifecycle-conversion-v1"),
            _action(
                EvidenceTargetKind.STORAGE_POLICY,
                policy.id,
                "lifecycle-policy-v1",
                action=EvidenceLifecycleAction.REJECTED,
            ),
        ]
    )

    previews = preflight_evidence_lifecycle_batch(db, document)
    assert {value.planned_action for value in previews} == {
        "deactivate_active_target"
    }
    result = apply_evidence_lifecycle_batch(db, document)
    assert result.changed_target_count == 2
    assert result.already_inactive_count == 0
    assert result.idempotent_count == 0
    assert len(result.events) == 2
    assert all(len(value.request_fingerprint) == 64 for value in result.events)

    conversion_row = db.get(DBIngredientConversionVersion, conversion.id)
    policy_row = db.get(DBStoragePolicyVersion, policy.id)
    assert conversion_row.active is False
    assert policy_row.active is False
    assert conversion_row.content_hash == conversion_hash
    assert policy_row.content_hash == policy_hash
    assert db.query(DBEvidenceLifecycleEvent).count() == 2

    retry = apply_evidence_lifecycle_batch(db, document)
    assert retry.changed_target_count == 0
    assert retry.idempotent_count == 2
    assert db.query(DBEvidenceLifecycleEvent).count() == 2


def test_contradictory_idempotency_key_is_rejected(db):
    first = register_conversion_version(db, _conversion("v1"))
    second = register_storage_policy_version(db, _policy("v1"))
    apply_evidence_lifecycle_batch(
        db,
        EvidenceLifecycleBatchDocument(
            actions=[
                _action(EvidenceTargetKind.CONVERSION, first.id, "shared-lifecycle-key")
            ]
        ),
    )
    conflicting = EvidenceLifecycleBatchDocument(
        actions=[
            _action(
                EvidenceTargetKind.STORAGE_POLICY,
                second.id,
                "shared-lifecycle-key",
            )
        ]
    )
    with pytest.raises(ValueError, match="different request"):
        apply_evidence_lifecycle_batch(db, conflicting)
    assert db.get(DBStoragePolicyVersion, second.id).active is True
    assert db.query(DBEvidenceLifecycleEvent).count() == 1


def test_unknown_target_rolls_back_other_lifecycle_actions(db):
    conversion = register_conversion_version(db, _conversion("v1"))
    document = EvidenceLifecycleBatchDocument(
        actions=[
            _action(EvidenceTargetKind.CONVERSION, conversion.id, "valid-before-unknown"),
            _action(EvidenceTargetKind.STORAGE_POLICY, 999999, "unknown-target"),
        ]
    )
    with pytest.raises(ValueError, match="Unknown storage_policy"):
        apply_evidence_lifecycle_batch(db, document)
    assert db.get(DBIngredientConversionVersion, conversion.id).active is True
    assert db.query(DBEvidenceLifecycleEvent).count() == 0


def test_successor_preserves_lineage_after_predecessor_deactivation(db):
    conversion = register_conversion_version(db, _conversion("v1"))
    policy = register_storage_policy_version(db, _policy("v1"))
    apply_evidence_lifecycle_batch(
        db,
        EvidenceLifecycleBatchDocument(
            actions=[
                _action(EvidenceTargetKind.CONVERSION, conversion.id, "deactivate-conversion-v1"),
                _action(EvidenceTargetKind.STORAGE_POLICY, policy.id, "deactivate-policy-v1"),
            ]
        ),
    )

    conversion_v2 = register_conversion_version(db, _conversion("v2", multiplier=118))
    policy_v2 = register_storage_policy_version(db, _policy("v2", hours=72))
    assert conversion_v2.supersedes_conversion_id == conversion.id
    assert policy_v2.supersedes_policy_id == policy.id
    assert conversion_v2.active is True
    assert policy_v2.active is True


def test_historical_leftover_link_survives_policy_deactivation(db):
    owner = DBUser(
        id="owner@example.test",
        name="Owner",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    household = DBHousehold(
        id="lifecycle-home",
        owner_user_id=owner.id,
        name="Lifecycle home",
        timezone="UTC",
        version=1,
    )
    recipe = DBRecipe(
        id="rice-recipe",
        name="Rice",
        description="",
        ingredients=["rice"],
        ingredient_data=[],
        servings=2,
        calories=200,
        macros={},
        flavor_profile={},
        tags=[],
        instructions=[],
        estimated_cost=2,
        nutrition_basis="per_serving",
    )
    db.add_all([owner, household, recipe])
    db.commit()
    policy = register_storage_policy_version(db, _policy("v1"))
    leftover = create_leftover(
        db,
        household,
        LeftoverCreate(
            recipe_id=recipe.id,
            portions_available=2,
            cooked_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            frozen=False,
            storage_policy_key="rice_refrigerated",
            idempotency_key="lifecycle-leftover-0001",
        ),
    )
    apply_evidence_lifecycle_batch(
        db,
        EvidenceLifecycleBatchDocument(
            actions=[
                _action(EvidenceTargetKind.STORAGE_POLICY, policy.id, "withdraw-policy-after-use")
            ]
        ),
    )

    linked = storage_policy_for_leftover(db, leftover.id)
    assert linked is not None
    assert linked.id == policy.id
    assert linked.active is False
    with pytest.raises(HTTPException) as exc:
        active_reviewed_storage_policy(db, "rice_refrigerated")
    assert exc.value.detail["code"] == "reviewed_storage_policy_unavailable"
    events = list_evidence_lifecycle_events(
        db,
        target_kind=EvidenceTargetKind.STORAGE_POLICY,
        target_id=policy.id,
    )
    assert len(events) == 1
    assert events[0].target_content_hash == policy.content_hash
