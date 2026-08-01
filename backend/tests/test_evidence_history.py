from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import (
    Base,
    DBHousehold,
    DBInventoryEvent,
    DBRecipe,
    DBUser,
)
from backend.domain.evidence_history import (
    ConversionApplicationRequest,
    EvidenceRecordStatus,
    IngredientConversionVersionInput,
    StoragePolicyVersionInput,
)
from backend.domain.inventory import LeftoverCreate
from backend.evidence_history_models import (
    DBIngredientConversionVersion,
    DBLeftoverStoragePolicyEvidence,
    DBStoragePolicyVersion,
)
from backend.services.evidence_history_service import (
    active_reviewed_storage_policy,
    apply_reviewed_conversion,
    list_conversion_versions,
    register_conversion_version,
    register_storage_policy_version,
    storage_policy_for_leftover,
)
from backend.services.inventory_service_v4 import create_leftover
from backend.services.official_evidence_history import (
    OFFICIAL_POLICY_VERSION,
    official_storage_policy_payloads,
    seed_official_storage_policy_versions,
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


def _reviewed_conversion(
    *,
    version: str = "v1",
    multiplier: float = 120.0,
    reviewed_at: datetime | None = None,
) -> IngredientConversionVersionInput:
    return IngredientConversionVersionInput(
        canonical_name=" Cooked Rice ",
        from_unit="cup",
        to_unit="g",
        record_version=version,
        multiplier_min=multiplier,
        multiplier_max=multiplier,
        source_name="Reviewed fixture",
        source_url="https://example.test/rice",
        source_version="source-1",
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=reviewed_at
        or datetime(2026, 7, 31, 6, 30, tzinfo=timezone.utc),
        reviewed_by="Evidence reviewer",
        notes="Exact fixture measure",
        active=True,
    )


def test_conversion_versions_are_immutable_idempotent_and_superseding(db):
    first = register_conversion_version(db, _reviewed_conversion())
    same_instant_different_offset = datetime.fromisoformat(
        "2026-07-31T12:00:00+05:30"
    )
    retry = register_conversion_version(
        db,
        _reviewed_conversion(reviewed_at=same_instant_different_offset),
    )
    assert retry.id == first.id
    assert retry.content_hash == first.content_hash

    with pytest.raises(ValueError, match="different evidence content"):
        register_conversion_version(
            db,
            _reviewed_conversion(multiplier=121.0),
        )

    successor = register_conversion_version(
        db,
        _reviewed_conversion(version="v2", multiplier=118.0),
    )
    assert successor.supersedes_conversion_id == first.id
    assert successor.active is True
    previous = db.get(DBIngredientConversionVersion, first.id)
    assert previous is not None and previous.active is False
    assert len(list_conversion_versions(db, active_only=False)) == 2


def test_reviewed_conversion_application_uses_exact_active_version(db):
    value = register_conversion_version(db, _reviewed_conversion())
    result = apply_reviewed_conversion(
        db,
        ConversionApplicationRequest(
            canonical_name="cooked rice",
            quantity_min=1.0,
            quantity_max=2.0,
            from_unit="CUP",
            to_unit="G",
        ),
    )
    assert result.output_quantity_min == 120.0
    assert result.output_quantity_max == 240.0
    assert result.conversion_record_id == value.id
    assert result.conversion_record_version == "v1"
    assert result.conversion_content_hash == value.content_hash

    with pytest.raises(HTTPException) as exc:
        apply_reviewed_conversion(
            db,
            ConversionApplicationRequest(
                canonical_name="cooked rice",
                quantity_min=1,
                quantity_max=1,
                from_unit="tbsp",
                to_unit="g",
            ),
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "reviewed_conversion_unavailable"


def test_storage_policy_versions_seed_idempotently_and_supersede(db):
    legacy = register_storage_policy_version(
        db,
        StoragePolicyVersionInput(
            policy_key="pizza_refrigerated",
            policy_version="legacy-reviewed-v1",
            food_category="pizza",
            storage_state="refrigerated",
            duration_min_hours=48,
            duration_max_hours=72,
            maximum_temperature_c=4,
            source_name="Legacy reviewed fixture",
            source_url="https://example.test/legacy",
            source_version="legacy",
            evidence_status=EvidenceRecordStatus.REVIEWED,
            reviewed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            reviewed_by="Legacy reviewer",
            safety_scope="general_home_storage",
            active=True,
        ),
    )
    created = seed_official_storage_policy_versions(db)
    assert created == len(official_storage_policy_payloads())
    assert seed_official_storage_policy_versions(db) == 0

    current = active_reviewed_storage_policy(db, "pizza_refrigerated")
    assert current.policy_version == OFFICIAL_POLICY_VERSION
    assert current.supersedes_policy_id == legacy.id
    old = db.get(DBStoragePolicyVersion, legacy.id)
    assert old is not None and old.active is False


def test_leftover_and_event_bind_exact_policy_version_atomically(db):
    seed_official_storage_policy_versions(db)
    user = DBUser(
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
        id="household-evidence",
        owner_user_id=user.id,
        name="Evidence home",
        timezone="UTC",
        version=1,
    )
    recipe = DBRecipe(
        id="pizza-recipe",
        name="Pizza",
        description="",
        ingredients=["pizza"],
        ingredient_data=[],
        servings=2,
        calories=400,
        macros={},
        flavor_profile={},
        tags=[],
        instructions=[],
        estimated_cost=5,
        nutrition_basis="per_serving",
    )
    db.add_all([user, household, recipe])
    db.commit()

    cooked_at = datetime(2026, 8, 1, 6, 0, tzinfo=timezone.utc)
    leftover = create_leftover(
        db,
        household,
        LeftoverCreate(
            recipe_id=recipe.id,
            portions_available=2,
            cooked_at=cooked_at,
            frozen=False,
            storage_policy_key="pizza_refrigerated",
            idempotency_key="leftover-evidence-0001",
        ),
    )
    policy = storage_policy_for_leftover(db, leftover.id)
    assert policy is not None
    assert policy.policy_version == OFFICIAL_POLICY_VERSION
    assert leftover.expires_at == cooked_at + timedelta(hours=96)

    link = (
        db.query(DBLeftoverStoragePolicyEvidence)
        .filter(DBLeftoverStoragePolicyEvidence.leftover_id == leftover.id)
        .one()
    )
    assert link.storage_policy_version_id == policy.id
    event = (
        db.query(DBInventoryEvent)
        .filter(DBInventoryEvent.leftover_id == leftover.id)
        .one()
    )
    assert event.event_metadata["storage_policy_version_id"] == policy.id
    assert event.event_metadata["storage_policy_version"] == policy.policy_version
    assert event.event_metadata["storage_policy_content_hash"] == policy.content_hash


def test_quality_guidance_does_not_create_safety_expiry(db):
    seed_official_storage_policy_versions(db)
    user = DBUser(
        id="frozen-owner@example.test",
        name="Owner",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    household = DBHousehold(
        id="frozen-household",
        owner_user_id=user.id,
        name="Frozen home",
        timezone="UTC",
        version=1,
    )
    recipe = DBRecipe(
        id="frozen-recipe",
        name="Frozen leftovers",
        description="",
        ingredients=["food"],
        ingredient_data=[],
        servings=1,
        calories=100,
        macros={},
        flavor_profile={},
        tags=[],
        instructions=[],
        estimated_cost=1,
        nutrition_basis="per_serving",
    )
    db.add_all([user, household, recipe])
    db.commit()
    leftover = create_leftover(
        db,
        household,
        LeftoverCreate(
            recipe_id=recipe.id,
            portions_available=1,
            cooked_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            frozen=True,
            storage_policy_key="cooked_leftovers_frozen_quality",
            idempotency_key="leftover-frozen-0001",
        ),
    )
    assert leftover.expires_at is None
    assert "not a safety expiry" in (leftover.notes or "")
