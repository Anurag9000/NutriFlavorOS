from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBInventoryEvent, DBRecipe, DBUser
from backend.domain.conversions import ConversionRequest
from backend.domain.inventory import HouseholdCreate, LeftoverCreate
from backend.services.conversion_service import (
    convert_quantity,
    import_fdc_portions,
    list_storage_policies,
    seed_official_storage_policies,
)
from backend.services.inventory_service_v4 import create_household, create_leftover


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _household_fixture(db):
    owner = DBUser(
        id="storage-owner@example.com",
        name="Storage Owner",
        hashed_password="x",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    recipe = DBRecipe(
        id="soup",
        name="Soup",
        description="",
        ingredients=["water"],
        ingredient_data=[],
        servings=2,
        calories=100,
        macros={"protein": 2, "carbs": 12, "fat": 3},
        flavor_profile={},
        tags=[],
        instructions=[],
        estimated_cost=1,
        nutrition_basis="per_serving",
    )
    db.add_all([owner, recipe])
    db.commit()
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    return household


def test_fdc_conversion_is_food_specific_and_preserves_missing_evidence():
    db = _db()
    count = import_fdc_portions(
        db,
        canonical_name="rolled oats",
        fdc_id=123,
        portions=[
            {
                "amount": 0.5,
                "gramWeight": 40,
                "measureUnit": {"name": "cup"},
            },
            {
                "amount": None,
                "gramWeight": 10,
                "measureUnit": {"name": "spoon"},
            },
        ],
        source_version="2026-04",
    )
    assert count == 1
    result = convert_quantity(
        db,
        ConversionRequest(
            canonical_name="rolled oats",
            quantity_min=1,
            quantity_max=2,
            from_unit="cup",
            to_unit="g",
        ),
    )
    assert result.output_quantity_min == 80
    assert result.output_quantity_max == 160
    with pytest.raises(HTTPException):
        convert_quantity(
            db,
            ConversionRequest(
                canonical_name="rice",
                quantity_min=1,
                quantity_max=1,
                from_unit="cup",
                to_unit="g",
            ),
        )


def test_only_reviewed_storage_policies_are_seeded_with_sources():
    db = _db()
    assert seed_official_storage_policies(db) >= 1
    rows = list_storage_policies(db, storage_state="refrigerated")
    assert rows
    assert all(row.source_url.startswith("https://") for row in rows)
    assert all(
        row.duration_max_hours is None
        or row.duration_max_hours >= row.duration_min_hours
        for row in rows
    )


def test_refrigerated_policy_derives_bounded_expiry_and_is_idempotent():
    db = _db()
    seed_official_storage_policies(db)
    household = _household_fixture(db)
    cooked_at = datetime.now(timezone.utc)
    payload = LeftoverCreate(
        recipe_id="soup",
        portions_available=2,
        cooked_at=cooked_at,
        frozen=False,
        storage_policy_key="cooked_leftovers_refrigerated_general",
        idempotency_key="reviewed-leftover-create-0001",
    )
    first = create_leftover(db, household, payload)
    repeated = create_leftover(db, household, payload)
    assert repeated.id == first.id
    assert first.expires_at == cooked_at + timedelta(hours=96)
    assert first.storage_policy_key == "cooked_leftovers_refrigerated_general"
    assert "cold-chain history" in first.notes
    assert (
        db.query(DBInventoryEvent)
        .filter(
            DBInventoryEvent.idempotency_key
            == "reviewed-leftover-create-0001"
        )
        .count()
        == 1
    )


def test_storage_policy_must_match_state_and_explicit_date_must_not_exceed_limit():
    db = _db()
    seed_official_storage_policies(db)
    household = _household_fixture(db)
    cooked_at = datetime.now(timezone.utc)

    with pytest.raises(HTTPException) as mismatch:
        create_leftover(
            db,
            household,
            LeftoverCreate(
                recipe_id="soup",
                portions_available=1,
                cooked_at=cooked_at,
                frozen=True,
                storage_policy_key="cooked_leftovers_refrigerated_general",
            ),
        )
    assert mismatch.value.status_code == 422
    assert mismatch.value.detail["code"] == "storage_policy_state_mismatch"

    with pytest.raises(HTTPException) as excessive:
        create_leftover(
            db,
            household,
            LeftoverCreate(
                recipe_id="soup",
                portions_available=1,
                cooked_at=cooked_at,
                expires_at=cooked_at + timedelta(days=5),
                frozen=False,
                storage_policy_key="cooked_leftovers_refrigerated_general",
            ),
        )
    assert excessive.value.status_code == 422
    assert excessive.value.detail["code"] == "expiry_exceeds_reviewed_policy"


def test_frozen_quality_policy_does_not_create_a_safety_expiry():
    db = _db()
    seed_official_storage_policies(db)
    household = _household_fixture(db)
    leftover = create_leftover(
        db,
        household,
        LeftoverCreate(
            recipe_id="soup",
            portions_available=1,
            cooked_at=datetime.now(timezone.utc),
            frozen=True,
            storage_policy_key="cooked_leftovers_frozen_quality",
            idempotency_key="frozen-quality-leftover-0001",
        ),
    )
    assert leftover.expires_at is None
    assert "quality guidance" in leftover.notes.lower()
    assert "not a safety expiry" in leftover.notes.lower()
