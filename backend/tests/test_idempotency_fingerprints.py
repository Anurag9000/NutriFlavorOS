from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBInventoryEvent, DBRecipe, DBUser
from backend.domain.inventory import (
    HouseholdCreate,
    InventoryMutation,
    LeftoverCreate,
    PantryItemCreate,
    QuantityRange,
)
from backend.services.idempotency_service import (
    request_fingerprint,
    run_idempotent_inventory_operation,
)
from backend.services.inventory_service import add_pantry_item, consume_pantry_item
from backend.services.inventory_service_v4 import create_household, create_leftover


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = Session()
    owner = DBUser(
        id="idempotency-owner@example.test",
        hashed_password="x",
        name="Owner",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    recipe = DBRecipe(
        id="idempotency-soup",
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
    session.add_all([owner, recipe])
    session.commit()
    try:
        yield session, owner
    finally:
        session.close()


def test_fingerprint_is_deterministic_and_excludes_transport_key():
    first = PantryItemCreate(
        ingredient_name="Rice",
        quantity=QuantityRange(quantity_min=1, quantity_max=1, unit="kg"),
        source="manual",
        metadata={"b": 2, "a": 1},
        idempotency_key="request-key-0001",
    )
    second = first.model_copy(update={"idempotency_key": "different-key-0002"})
    assert request_fingerprint(operation="pantry_create", payload=first) == request_fingerprint(
        operation="pantry_create", payload=second
    )
    assert request_fingerprint(operation="pantry_create", payload=first) != request_fingerprint(
        operation="leftover_create", payload=first
    )


def test_pantry_creation_retries_match_complete_request(db):
    session, owner = db
    household = create_household(session, owner, HouseholdCreate(name="Home"))
    payload = PantryItemCreate(
        ingredient_name="Rice",
        display_name="Basmati rice",
        quantity=QuantityRange(quantity_min=500, quantity_max=750, unit="g"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        source="manual",
        metadata={"package": "opened"},
        idempotency_key="pantry-full-request-0001",
    )

    def execute(value: PantryItemCreate):
        return run_idempotent_inventory_operation(
            session,
            household_id=household.id,
            key=value.idempotency_key,
            operation="pantry_create",
            payload=value,
            handler=lambda: add_pantry_item(session, household, value),
        )

    first = execute(payload)
    repeated = execute(payload)
    assert repeated.id == first.id
    assert session.query(DBInventoryEvent).count() == 1
    event = session.query(DBInventoryEvent).one()
    assert len(event.event_metadata["request_fingerprint"]) == 64
    assert event.event_metadata["idempotency_operation"] == "pantry_create"

    changed_expiry = payload.model_copy(
        update={"expires_at": payload.expires_at + timedelta(days=1)}
    )
    with pytest.raises(HTTPException) as conflict:
        execute(changed_expiry)
    assert conflict.value.status_code == 409
    assert conflict.value.detail["code"] == "idempotency_key_reused"
    assert session.query(DBInventoryEvent).count() == 1


def test_pantry_mutation_context_and_reason_are_fingerprinted(db):
    session, owner = db
    household = create_household(session, owner, HouseholdCreate(name="Home"))
    item = add_pantry_item(
        session,
        household,
        PantryItemCreate(
            ingredient_name="rice",
            quantity=QuantityRange(quantity_min=500, quantity_max=500, unit="g"),
        ),
    )
    payload = InventoryMutation(
        quantity=QuantityRange(quantity_min=100, quantity_max=100, unit="g"),
        expected_version=1,
        reason="prepared dinner",
        idempotency_key="pantry-consume-full-0001",
    )

    def execute(value: InventoryMutation, item_id: int = item.id):
        return run_idempotent_inventory_operation(
            session,
            household_id=household.id,
            key=value.idempotency_key,
            operation="pantry_consume",
            payload=value,
            context={"item_id": item_id},
            handler=lambda: consume_pantry_item(
                session, household, item_id, value
            ),
        )

    first = execute(payload)
    repeated = execute(payload)
    assert first.quantity_max == repeated.quantity_max == 400

    with pytest.raises(HTTPException) as changed_reason:
        execute(payload.model_copy(update={"reason": "different use"}))
    assert changed_reason.value.detail["code"] == "idempotency_key_reused"

    with pytest.raises(HTTPException) as changed_target:
        execute(payload, item_id=item.id + 1)
    assert changed_target.value.detail["code"] == "idempotency_key_reused"


def test_leftover_metadata_changes_cannot_reuse_a_key(db):
    session, owner = db
    household = create_household(session, owner, HouseholdCreate(name="Home"))
    payload = LeftoverCreate(
        recipe_id="idempotency-soup",
        portions_available=2,
        cooked_at=datetime.now(timezone.utc),
        frozen=False,
        notes="refrigerated promptly",
        idempotency_key="leftover-full-request-0001",
    )

    def execute(value: LeftoverCreate):
        return run_idempotent_inventory_operation(
            session,
            household_id=household.id,
            key=value.idempotency_key,
            operation="leftover_create",
            payload=value,
            handler=lambda: create_leftover(session, household, value),
        )

    first = execute(payload)
    repeated = execute(payload)
    assert repeated.id == first.id

    with pytest.raises(HTTPException) as changed_storage:
        execute(payload.model_copy(update={"frozen": True}))
    assert changed_storage.value.detail["code"] == "idempotency_key_reused"

    with pytest.raises(HTTPException) as changed_notes:
        execute(payload.model_copy(update={"notes": "left at room temperature"}))
    assert changed_notes.value.detail["code"] == "idempotency_key_reused"


def test_legacy_key_without_fingerprint_is_rejected_as_ambiguous(db):
    session, owner = db
    household = create_household(session, owner, HouseholdCreate(name="Home"))
    payload = PantryItemCreate(
        ingredient_name="rice",
        quantity=QuantityRange(quantity_min=100, quantity_max=100, unit="g"),
        idempotency_key="legacy-event-key-0001",
    )
    add_pantry_item(session, household, payload)

    with pytest.raises(HTTPException) as conflict:
        run_idempotent_inventory_operation(
            session,
            household_id=household.id,
            key=payload.idempotency_key,
            operation="pantry_create",
            payload=payload,
            handler=lambda: add_pantry_item(session, household, payload),
        )
    assert conflict.value.status_code == 409
    assert "legacy event" in conflict.value.detail["message"].lower()
