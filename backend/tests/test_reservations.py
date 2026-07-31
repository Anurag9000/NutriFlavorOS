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
    DBMealPlan,
    DBPantryItem,
    DBStockReservation,
    DBUser,
)
from backend.domain.household_access import ReservationMutation, ReservationStatus
from backend.domain.inventory import ReconciledShoppingItem
from backend.services.reservation_service import (
    commit_plan_reservations,
    create_plan_reservations,
    release_plan_reservations,
    usable_pantry_intervals,
)


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _fixture_state():
    db = _db()
    now = datetime.now(timezone.utc)
    user = DBUser(
        id="u@example.com",
        name="U",
        hashed_password="x",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    db.add(user)
    db.flush()
    household = DBHousehold(
        id="h",
        owner_user_id=user.id,
        name="H",
        timezone="UTC",
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(household)
    db.flush()
    early = DBPantryItem(
        household_id="h",
        canonical_name="rice",
        display_name="Rice",
        quantity_min=100,
        quantity_max=100,
        unit="g",
        expires_at=now + timedelta(days=1),
        source="manual",
        item_metadata={},
        version=1,
        created_at=now,
        updated_at=now,
    )
    late = DBPantryItem(
        household_id="h",
        canonical_name="rice",
        display_name="Rice",
        quantity_min=100,
        quantity_max=100,
        unit="g",
        expires_at=now + timedelta(days=10),
        source="manual",
        item_metadata={},
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add_all([early, late])
    db.flush()
    first_plan = DBMealPlan(
        user_id=user.id,
        household_id="h",
        schema_version="2",
        plan_data={},
    )
    second_plan = DBMealPlan(
        user_id=user.id,
        household_id="h",
        schema_version="2",
        plan_data={},
    )
    db.add_all([first_plan, second_plan])
    db.commit()
    return db, household, early, late, first_plan, second_plan


def _need(amount: float) -> ReconciledShoppingItem:
    return ReconciledShoppingItem(
        canonical_name="rice",
        display_name="Rice",
        unit="g",
        required_min=amount,
        required_max=amount,
        pantry_min=200,
        pantry_max=200,
        buy_min=0,
        buy_max=0,
        coverage_status="covered",
    )


def test_reservation_uses_expiry_order_and_subtracts_only_on_commit():
    db, household, early, late, plan, _ = _fixture_state()
    rows = create_plan_reservations(
        db,
        household=household,
        plan=plan,
        shopping=[_need(150)],
        reservation_hours=24,
    )
    assert rows[0].pantry_item_id == early.id
    assert sum(row.quantity_max for row in rows) == 150
    assert db.get(DBPantryItem, early.id).quantity_max == 100
    intervals = usable_pantry_intervals(db, "h")
    assert intervals[("rice", "g")]["max"] == 50

    committed = commit_plan_reservations(
        db, "h", plan.id, ReservationMutation(reason="prepared")
    )
    repeated = commit_plan_reservations(
        db, "h", plan.id, ReservationMutation(reason="retry")
    )
    assert [row.id for row in repeated] == [row.id for row in committed]
    assert all(row.status == ReservationStatus.CONSUMED.value for row in repeated)
    assert db.get(DBPantryItem, early.id).quantity_max == 0
    assert db.get(DBPantryItem, late.id).quantity_max == 50
    assert (
        db.query(DBInventoryEvent)
        .filter(DBInventoryEvent.event_type == "reservation_commit")
        .count()
        == 2
    )


def test_same_plan_creation_is_idempotent_and_other_plan_cannot_overbook():
    db, household, _early, _late, first_plan, second_plan = _fixture_state()
    first = create_plan_reservations(
        db,
        household=household,
        plan=first_plan,
        shopping=[_need(150)],
        reservation_hours=24,
    )
    repeated = create_plan_reservations(
        db,
        household=household,
        plan=first_plan,
        shopping=[_need(150)],
        reservation_hours=24,
    )
    assert [row.id for row in repeated] == [row.id for row in first]

    second = create_plan_reservations(
        db,
        household=household,
        plan=second_plan,
        shopping=[_need(150)],
        reservation_hours=24,
    )
    assert sum(row.quantity_max for row in first) == 150
    assert sum(row.quantity_max for row in second) == 50
    assert (
        db.query(DBStockReservation)
        .filter(DBStockReservation.status == ReservationStatus.ACTIVE.value)
        .with_entities(DBStockReservation.quantity_max)
        .all()
    )
    active_total = sum(
        row.quantity_max
        for row in db.query(DBStockReservation)
        .filter(DBStockReservation.status == ReservationStatus.ACTIVE.value)
        .all()
    )
    assert active_total == 200


def test_release_is_idempotent():
    db, household, _early, _late, plan, _ = _fixture_state()
    created = create_plan_reservations(
        db,
        household=household,
        plan=plan,
        shopping=[_need(50)],
        reservation_hours=24,
    )
    released = release_plan_reservations(
        db, household.id, plan.id, ReservationMutation(reason="cancelled")
    )
    repeated = release_plan_reservations(
        db, household.id, plan.id, ReservationMutation(reason="retry")
    )
    assert [row.id for row in released] == [row.id for row in created]
    assert [row.id for row in repeated] == [row.id for row in released]
    assert all(row.status == ReservationStatus.RELEASED.value for row in repeated)


def test_expired_status_is_committed_before_error_is_returned():
    db, household, _early, _late, plan, _ = _fixture_state()
    created = create_plan_reservations(
        db,
        household=household,
        plan=plan,
        shopping=[_need(50)],
        reservation_hours=24,
    )
    for row in created:
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        commit_plan_reservations(
            db, household.id, plan.id, ReservationMutation(reason="late")
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "reservation_expired"
    db.expire_all()
    persisted = db.get(DBStockReservation, created[0].id)
    assert persisted.status == ReservationStatus.EXPIRED.value
    assert persisted.version == 2
