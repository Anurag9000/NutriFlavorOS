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
    LeftoverConsume,
    LeftoverCreate,
    PantryItemCreate,
    QuantityRange,
)
from backend.models import DailyPlan, PlanResponse, Recipe
from backend.services.inventory_service import (
    add_pantry_item,
    build_batch_prep_tasks,
    consume_leftover,
    consume_pantry_item,
    create_household,
    create_leftover,
    list_pantry_items,
    reconcile_shopping_list,
)


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
    session.add(
        DBUser(
            id="owner@example.com",
            hashed_password="x",
            name="Owner",
            allergies=[],
            dietary_restrictions=[],
            disliked_ingredients=[],
            liked_ingredients=[],
            health_conditions=[],
            medications=[],
        )
    )
    session.add(
        DBRecipe(
            id="rice-bowl",
            name="Rice Bowl",
            description="",
            ingredients=["200 g rice"],
            ingredient_data=[],
            servings=1,
            calories=300,
            macros={"protein": 8, "carbs": 60, "fat": 3},
            flavor_profile={},
            tags=[],
            instructions=[],
            estimated_cost=2,
            nutrition_basis="per_serving",
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_inventory_is_canonical_idempotent_and_versioned(db):
    owner = db.get(DBUser, "owner@example.com")
    household = create_household(
        db, owner, HouseholdCreate(name="Home", timezone="Asia/Kolkata")
    )
    payload = PantryItemCreate(
        ingredient_name="Rice",
        quantity=QuantityRange(quantity_min=1, quantity_max=1, unit="kg"),
        idempotency_key="purchase-rice-0001",
    )
    first = add_pantry_item(db, household, payload)
    second = add_pantry_item(db, household, payload)
    assert first.id == second.id
    assert first.unit == "g"
    assert first.quantity_min == first.quantity_max == 1000
    assert db.query(DBInventoryEvent).count() == 1

    mutation = InventoryMutation(
        quantity=QuantityRange(quantity_min=200, quantity_max=200, unit="g"),
        expected_version=1,
        idempotency_key="consume-rice-0001",
    )
    consumed = consume_pantry_item(db, household, first.id, mutation)
    repeated = consume_pantry_item(db, household, first.id, mutation)
    assert repeated.id == consumed.id
    assert repeated.quantity_min == repeated.quantity_max == 800
    assert repeated.version == 2
    assert db.query(DBInventoryEvent).count() == 2

    with pytest.raises(HTTPException) as exc:
        consume_pantry_item(
            db,
            household,
            first.id,
            InventoryMutation(
                quantity=QuantityRange(
                    quantity_min=1, quantity_max=1, unit="g"
                ),
                expected_version=1,
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "stale_version"


def test_idempotency_key_cannot_be_reused_for_a_different_request(db):
    owner = db.get(DBUser, "owner@example.com")
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    item = add_pantry_item(
        db,
        household,
        PantryItemCreate(
            ingredient_name="rice",
            quantity=QuantityRange(quantity_min=500, quantity_max=500, unit="g"),
            idempotency_key="purchase-rice-conflict-0001",
        ),
    )

    with pytest.raises(HTTPException) as purchase_conflict:
        add_pantry_item(
            db,
            household,
            PantryItemCreate(
                ingredient_name="lentils",
                quantity=QuantityRange(
                    quantity_min=500, quantity_max=500, unit="g"
                ),
                idempotency_key="purchase-rice-conflict-0001",
            ),
        )
    assert purchase_conflict.value.status_code == 409
    assert purchase_conflict.value.detail["code"] == "idempotency_key_reused"

    consume_pantry_item(
        db,
        household,
        item.id,
        InventoryMutation(
            quantity=QuantityRange(quantity_min=100, quantity_max=100, unit="g"),
            idempotency_key="consume-rice-conflict-0001",
        ),
    )
    with pytest.raises(HTTPException) as mutation_conflict:
        consume_pantry_item(
            db,
            household,
            item.id,
            InventoryMutation(
                quantity=QuantityRange(
                    quantity_min=101, quantity_max=101, unit="g"
                ),
                idempotency_key="consume-rice-conflict-0001",
            ),
        )
    assert mutation_conflict.value.status_code == 409
    assert mutation_conflict.value.detail["code"] == "idempotency_key_reused"


def test_shopping_reconciliation_uses_ranges_and_ignores_expired(db):
    owner = db.get(DBUser, "owner@example.com")
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    add_pantry_item(
        db,
        household,
        PantryItemCreate(
            ingredient_name="rice",
            quantity=QuantityRange(quantity_min=0.7, quantity_max=0.8, unit="kg"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        ),
    )
    add_pantry_item(
        db,
        household,
        PantryItemCreate(
            ingredient_name="rice",
            quantity=QuantityRange(quantity_min=500, quantity_max=500, unit="g"),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        ),
    )
    recipe = Recipe(
        id="rice-bowl",
        name="Rice Bowl",
        description="",
        ingredients=["200 g rice"],
        calories=300,
        macros={"protein": 8, "carbs": 60, "fat": 3},
    )
    plan = PlanResponse(
        user_id=owner.id,
        days=[
            DailyPlan(
                day=1,
                meals={"Dinner": recipe},
                portions={"Dinner": 1},
                total_stats={},
                scores={},
            )
        ],
        shopping_list={
            "Grains": {
                "rice": {
                    "display_name": "Rice",
                    "quantities": [
                        {
                            "quantity_min": 1000,
                            "quantity_max": 1200,
                            "unit": "g",
                        }
                    ],
                    "source_recipe_ids": ["rice-bowl"],
                }
            }
        },
    )
    item = reconcile_shopping_list(
        plan, list_pantry_items(db, household.id)
    )[0]
    assert item.pantry_min == 700
    assert item.pantry_max == 800
    assert item.buy_min == 200
    assert item.buy_max == 500
    assert item.coverage_status == "partial"
    assert item.expiring_quantity_max == 800


def test_leftover_ledger_is_idempotent_and_batch_prep_requires_reviewed_policy(db):
    owner = db.get(DBUser, "owner@example.com")
    household = create_household(db, owner, HouseholdCreate(name="Home"))
    leftover = create_leftover(
        db,
        household,
        LeftoverCreate(
            recipe_id="rice-bowl",
            portions_available=3,
            cooked_at=datetime.now(timezone.utc),
            idempotency_key="leftover-create-0001",
        ),
    )
    mutation = LeftoverConsume(
        portions=1.25,
        expected_version=1,
        idempotency_key="leftover-eat-0001",
    )
    remaining = consume_leftover(db, household, leftover.id, mutation)
    repeated = consume_leftover(db, household, leftover.id, mutation)
    assert repeated.id == remaining.id
    assert repeated.portions_available == pytest.approx(1.75)
    assert repeated.version == 2

    with pytest.raises(HTTPException) as conflict:
        consume_leftover(
            db,
            household,
            leftover.id,
            LeftoverConsume(
                portions=0.5,
                idempotency_key="leftover-eat-0001",
            ),
        )
    assert conflict.value.detail["code"] == "idempotency_key_reused"

    recipe = Recipe(
        id="rice-bowl",
        name="Rice Bowl",
        description="",
        ingredients=["200 g rice"],
        calories=300,
        macros={"protein": 8, "carbs": 60, "fat": 3},
    )
    plan = PlanResponse(
        user_id=owner.id,
        days=[
            DailyPlan(
                day=1,
                meals={"Dinner": recipe},
                portions={"Dinner": 1.5},
                total_stats={},
                scores={},
            ),
            DailyPlan(
                day=3,
                meals={"Lunch": recipe},
                portions={"Lunch": 1.0},
                total_stats={},
                scores={},
            ),
        ],
    )
    task = build_batch_prep_tasks(plan)[0]
    assert task.total_portions == 2.5
    assert task.occurrences == 2
    assert task.storage_guidance_status == "requires_reviewed_recipe_specific_policy"
