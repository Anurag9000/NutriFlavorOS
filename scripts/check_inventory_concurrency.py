#!/usr/bin/env python3
"""Exercise PostgreSQL inventory and reservation concurrency contracts.

This script runs after a fresh PostgreSQL Alembic migration in CI. SQLite is
supported for local development, but it cannot validate the same row-lock
semantics used by hosted concurrent deployments.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any, Dict
from uuid import uuid4

from fastapi import HTTPException

from backend.database import (
    DBHousehold,
    DBInventoryEvent,
    DBMealPlan,
    DBPantryItem,
    DBStockReservation,
    DBUser,
    DB_URL,
    SessionLocal,
)
from backend.domain.household_access import ReservationMutation, ReservationStatus
from backend.domain.inventory import (
    HouseholdCreate,
    InventoryMutation,
    PantryItemCreate,
    QuantityRange,
    ReconciledShoppingItem,
)
from backend.services.inventory_service import add_pantry_item, consume_pantry_item
from backend.services.inventory_service_v4 import create_household
from backend.services.reservation_service import (
    commit_plan_reservations,
    create_plan_reservations,
)


def _assert_postgresql() -> None:
    if not DB_URL.startswith("postgresql"):
        raise RuntimeError(
            "check_inventory_concurrency.py requires a PostgreSQL DATABASE_URL"
        )


def _setup() -> tuple[str, str, int]:
    session = SessionLocal()
    try:
        suffix = uuid4().hex
        user = DBUser(
            id=f"inventory-concurrency-{suffix}@example.test",
            hashed_password="not-used-by-this-probe",
            name="Inventory Concurrency Probe",
            liked_ingredients=[],
            disliked_ingredients=[],
            allergies=[],
            dietary_restrictions=[],
            health_conditions=[],
            medications=[],
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        household = create_household(
            session,
            user,
            HouseholdCreate(name=f"Concurrency {suffix}", timezone="UTC"),
        )
        item = add_pantry_item(
            session,
            household,
            PantryItemCreate(
                ingredient_name="rice",
                quantity=QuantityRange(
                    quantity_min=1000,
                    quantity_max=1000,
                    unit="g",
                ),
                idempotency_key=f"purchase-{suffix}",
            ),
        )
        return user.id, household.id, item.id
    finally:
        session.close()


def _consume(
    barrier: Barrier,
    household_id: str,
    item_id: int,
    *,
    amount: float,
    key: str,
    expected_version: int | None,
) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        household = session.get(DBHousehold, household_id)
        if household is None:
            raise AssertionError("Household disappeared during concurrency probe")
        barrier.wait(timeout=20)
        item = consume_pantry_item(
            session,
            household,
            item_id,
            InventoryMutation(
                quantity=QuantityRange(
                    quantity_min=amount,
                    quantity_max=amount,
                    unit="g",
                ),
                expected_version=expected_version,
                idempotency_key=key,
            ),
        )
        return {
            "status": "success",
            "version": item.version,
            "quantity_min": item.quantity_min,
            "quantity_max": item.quantity_max,
        }
    except HTTPException as exc:
        session.rollback()
        return {"status": "http_error", "code": exc.status_code, "detail": exc.detail}
    finally:
        session.close()


def _run_identical_retry_probe(household_id: str, item_id: int) -> None:
    key = f"identical-{uuid4().hex}"
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: _consume(
                    barrier,
                    household_id,
                    item_id,
                    amount=100,
                    key=key,
                    expected_version=1,
                ),
                range(2),
            )
        )
    assert [result["status"] for result in results] == ["success", "success"], results

    session = SessionLocal()
    try:
        item = session.get(DBPantryItem, item_id)
        assert item is not None
        assert item.quantity_min == item.quantity_max == 900
        assert item.version == 2
        events = (
            session.query(DBInventoryEvent)
            .filter(
                DBInventoryEvent.household_id == household_id,
                DBInventoryEvent.idempotency_key == key,
            )
            .all()
        )
        assert len(events) == 1
    finally:
        session.close()


def _run_competing_version_probe(household_id: str, item_id: int) -> None:
    barrier = Barrier(2)
    keys = [f"competing-{uuid4().hex}", f"competing-{uuid4().hex}"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _consume,
                barrier,
                household_id,
                item_id,
                amount=100,
                key=key,
                expected_version=2,
            )
            for key in keys
        ]
        results = [future.result(timeout=30) for future in futures]

    successes = [result for result in results if result["status"] == "success"]
    conflicts = [result for result in results if result["status"] == "http_error"]
    assert len(successes) == 1, results
    assert len(conflicts) == 1, results
    assert conflicts[0]["code"] == 409, conflicts
    assert isinstance(conflicts[0]["detail"], dict), conflicts
    assert conflicts[0]["detail"].get("code") == "stale_version", conflicts

    session = SessionLocal()
    try:
        item = session.get(DBPantryItem, item_id)
        assert item is not None
        assert item.quantity_min == item.quantity_max == 800
        assert item.version == 3
        event_count = (
            session.query(DBInventoryEvent)
            .filter(DBInventoryEvent.idempotency_key.in_(keys))
            .count()
        )
        assert event_count == 1
    finally:
        session.close()


def _create_item_and_plans(
    user_id: str,
    household_id: str,
    ingredient: str,
    quantity: float,
    plan_count: int,
) -> tuple[int, list[int]]:
    session = SessionLocal()
    try:
        household = session.get(DBHousehold, household_id)
        if household is None:
            raise AssertionError("Household disappeared during reservation setup")
        item = add_pantry_item(
            session,
            household,
            PantryItemCreate(
                ingredient_name=ingredient,
                quantity=QuantityRange(
                    quantity_min=quantity,
                    quantity_max=quantity,
                    unit="g",
                ),
                idempotency_key=f"purchase-{ingredient}-{uuid4().hex}",
            ),
        )
        plans = [
            DBMealPlan(
                user_id=user_id,
                household_id=household_id,
                schema_version="2",
                plan_data={},
            )
            for _ in range(plan_count)
        ]
        session.add_all(plans)
        session.commit()
        return item.id, [plan.id for plan in plans]
    finally:
        session.close()


def _reserve(
    barrier: Barrier,
    household_id: str,
    plan_id: int,
    ingredient: str,
    amount: float,
) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        household = session.get(DBHousehold, household_id)
        plan = session.get(DBMealPlan, plan_id)
        if household is None or plan is None:
            raise AssertionError("Reservation fixture disappeared")
        barrier.wait(timeout=20)
        rows = create_plan_reservations(
            session,
            household=household,
            plan=plan,
            shopping=[
                ReconciledShoppingItem(
                    canonical_name=ingredient,
                    display_name=ingredient.title(),
                    unit="g",
                    required_min=amount,
                    required_max=amount,
                    pantry_min=amount,
                    pantry_max=amount,
                    buy_min=0,
                    buy_max=0,
                    coverage_status="covered",
                )
            ],
            reservation_hours=24,
        )
        return {
            "status": "success",
            "ids": [row.id for row in rows],
            "quantity_max": sum(float(row.quantity_max) for row in rows),
        }
    except HTTPException as exc:
        session.rollback()
        return {"status": "http_error", "code": exc.status_code, "detail": exc.detail}
    finally:
        session.close()


def _run_cross_plan_non_overbooking_probe(
    user_id: str, household_id: str
) -> None:
    item_id, plan_ids = _create_item_and_plans(
        user_id, household_id, "lentils", 1000, 2
    )
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _reserve,
                barrier,
                household_id,
                plan_id,
                "lentils",
                700,
            )
            for plan_id in plan_ids
        ]
        results = [future.result(timeout=30) for future in futures]
    assert all(result["status"] == "success" for result in results), results
    assert sorted(result["quantity_max"] for result in results) == [300, 700], results

    session = SessionLocal()
    try:
        total = sum(
            float(row.quantity_max)
            for row in session.query(DBStockReservation)
            .filter(
                DBStockReservation.pantry_item_id == item_id,
                DBStockReservation.status == ReservationStatus.ACTIVE.value,
            )
            .all()
        )
        assert total == 1000
    finally:
        session.close()


def _commit(
    barrier: Barrier, household_id: str, plan_id: int
) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        barrier.wait(timeout=20)
        rows = commit_plan_reservations(
            session,
            household_id,
            plan_id,
            ReservationMutation(reason="concurrency probe"),
        )
        return {"status": "success", "ids": [row.id for row in rows]}
    except HTTPException as exc:
        session.rollback()
        return {"status": "http_error", "code": exc.status_code, "detail": exc.detail}
    finally:
        session.close()


def _run_same_plan_retry_and_commit_probe(
    user_id: str, household_id: str
) -> None:
    item_id, plan_ids = _create_item_and_plans(
        user_id, household_id, "beans", 500, 1
    )
    plan_id = plan_ids[0]
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _reserve,
                barrier,
                household_id,
                plan_id,
                "beans",
                400,
            )
            for _ in range(2)
        ]
        creation_results = [future.result(timeout=30) for future in futures]
    assert all(result["status"] == "success" for result in creation_results), creation_results
    assert creation_results[0]["ids"] == creation_results[1]["ids"], creation_results

    commit_barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_commit, commit_barrier, household_id, plan_id)
            for _ in range(2)
        ]
        commit_results = [future.result(timeout=30) for future in futures]
    assert all(result["status"] == "success" for result in commit_results), commit_results
    assert commit_results[0]["ids"] == commit_results[1]["ids"], commit_results

    session = SessionLocal()
    try:
        item = session.get(DBPantryItem, item_id)
        assert item is not None
        assert item.quantity_min == item.quantity_max == 100
        events = (
            session.query(DBInventoryEvent)
            .filter(
                DBInventoryEvent.pantry_item_id == item_id,
                DBInventoryEvent.event_type == "reservation_commit",
            )
            .all()
        )
        assert len(events) == 1
    finally:
        session.close()


def main() -> None:
    _assert_postgresql()
    user_id, household_id, item_id = _setup()
    _run_identical_retry_probe(household_id, item_id)
    _run_competing_version_probe(household_id, item_id)
    _run_cross_plan_non_overbooking_probe(user_id, household_id)
    _run_same_plan_retry_and_commit_probe(user_id, household_id)
    print("PostgreSQL inventory and reservation concurrency probes passed")


if __name__ == "__main__":
    main()
