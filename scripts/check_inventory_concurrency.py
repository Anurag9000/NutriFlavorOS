#!/usr/bin/env python3
"""Exercise PostgreSQL row locks, idempotency, and optimistic versions.

This script is intentionally run after a fresh PostgreSQL Alembic migration in
CI. SQLite remains supported for local development, but it cannot validate the
same row-lock semantics used by hosted concurrent deployments.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any, Dict
from uuid import uuid4

from fastapi import HTTPException

from backend.database import (
    DBInventoryEvent,
    DBPantryItem,
    DBUser,
    DB_URL,
    SessionLocal,
)
from backend.domain.inventory import (
    HouseholdCreate,
    InventoryMutation,
    PantryItemCreate,
    QuantityRange,
)
from backend.services.inventory_service import add_pantry_item, consume_pantry_item
from backend.services.inventory_service_v4 import create_household


def _assert_postgresql() -> None:
    if not DB_URL.startswith("postgresql"):
        raise RuntimeError(
            "check_inventory_concurrency.py requires a PostgreSQL DATABASE_URL"
        )


def _setup() -> tuple[str, int]:
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
        return household.id, item.id
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
        from backend.database import DBHousehold

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


def main() -> None:
    _assert_postgresql()
    household_id, item_id = _setup()
    _run_identical_retry_probe(household_id, item_id)
    _run_competing_version_probe(household_id, item_id)
    print("PostgreSQL inventory concurrency probe passed")


if __name__ == "__main__":
    main()
