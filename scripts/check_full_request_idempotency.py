#!/usr/bin/env python3
"""Exercise full-request inventory idempotency on PostgreSQL.

The unit suite covers deterministic fingerprints in-process. This probe runs
against PostgreSQL so the advisory-lock path is exercised with independent
sessions and concurrent workers.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from backend.database import (
    DBHousehold,
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
from backend.services.idempotency_service import run_idempotent_inventory_operation
from backend.services.inventory_service import add_pantry_item, consume_pantry_item
from backend.services.inventory_service_v4 import create_household


def _assert_postgresql() -> None:
    if not DB_URL.startswith("postgresql"):
        raise RuntimeError(
            "check_full_request_idempotency.py requires a PostgreSQL DATABASE_URL"
        )


def _fixture(ingredient: str) -> tuple[str, int]:
    session = SessionLocal()
    try:
        suffix = uuid4().hex
        owner = DBUser(
            id=f"full-idempotency-{suffix}@example.test",
            hashed_password="not-used-by-this-probe",
            name="Full Idempotency Probe",
            liked_ingredients=[],
            disliked_ingredients=[],
            allergies=[],
            dietary_restrictions=[],
            health_conditions=[],
            medications=[],
        )
        session.add(owner)
        session.commit()
        household = create_household(
            session,
            owner,
            HouseholdCreate(name=f"Idempotency {suffix}", timezone="UTC"),
        )
        item = add_pantry_item(
            session,
            household,
            PantryItemCreate(
                ingredient_name=ingredient,
                quantity=QuantityRange(
                    quantity_min=1000,
                    quantity_max=1000,
                    unit="g",
                ),
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
    reason: str,
    key: str,
) -> dict[str, Any]:
    session = SessionLocal()
    try:
        household = session.get(DBHousehold, household_id)
        if household is None:
            raise AssertionError("Household disappeared during idempotency probe")
        payload = InventoryMutation(
            quantity=QuantityRange(
                quantity_min=amount,
                quantity_max=amount,
                unit="g",
            ),
            expected_version=1,
            reason=reason,
            idempotency_key=key,
        )
        barrier.wait(timeout=20)
        item = run_idempotent_inventory_operation(
            session,
            household_id=household_id,
            key=key,
            operation="pantry_consume",
            payload=payload,
            context={"item_id": item_id},
            handler=lambda: consume_pantry_item(
                session,
                household,
                item_id,
                payload,
            ),
        )
        return {
            "status": "success",
            "quantity": float(item.quantity_max),
            "version": int(item.version),
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "status": "http_error",
            "code": exc.status_code,
            "detail": exc.detail,
        }
    finally:
        session.close()


def _events(household_id: str, key: str) -> list[DBInventoryEvent]:
    session = SessionLocal()
    try:
        return (
            session.query(DBInventoryEvent)
            .filter(
                DBInventoryEvent.household_id == household_id,
                DBInventoryEvent.idempotency_key == key,
            )
            .all()
        )
    finally:
        session.close()


def _assert_item(item_id: int, *, expected_quantities: set[float]) -> None:
    session = SessionLocal()
    try:
        item = session.get(DBPantryItem, item_id)
        assert item is not None
        assert float(item.quantity_min) == float(item.quantity_max)
        assert float(item.quantity_max) in expected_quantities
        assert item.version == 2
    finally:
        session.close()


def identical_retry_probe() -> None:
    household_id, item_id = _fixture("rice")
    key = f"identical-full-{uuid4().hex}"
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _consume,
                barrier,
                household_id,
                item_id,
                amount=100,
                reason="same request",
                key=key,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert all(result["status"] == "success" for result in results), results
    assert all(result["quantity"] == 900 for result in results), results
    _assert_item(item_id, expected_quantities={900.0})
    events = _events(household_id, key)
    assert len(events) == 1
    metadata = dict(events[0].event_metadata or {})
    assert len(str(metadata.get("request_fingerprint", ""))) == 64
    assert metadata.get("idempotency_operation") == "pantry_consume"
    assert metadata.get("idempotency_context") == {"item_id": item_id}


def contradictory_retry_probe() -> None:
    household_id, item_id = _fixture("lentils")
    key = f"contradictory-full-{uuid4().hex}"
    barrier = Barrier(2)
    requests = [(25.0, "first body"), (50.0, "different body")]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _consume,
                barrier,
                household_id,
                item_id,
                amount=amount,
                reason=reason,
                key=key,
            )
            for amount, reason in requests
        ]
        results = [future.result(timeout=30) for future in futures]

    successes = [result for result in results if result["status"] == "success"]
    conflicts = [result for result in results if result["status"] == "http_error"]
    assert len(successes) == 1, results
    assert len(conflicts) == 1, results
    assert conflicts[0]["code"] == 409, conflicts
    assert isinstance(conflicts[0]["detail"], dict), conflicts
    assert conflicts[0]["detail"].get("code") == "idempotency_key_reused", conflicts
    _assert_item(item_id, expected_quantities={950.0, 975.0})
    events = _events(household_id, key)
    assert len(events) == 1
    assert len(str((events[0].event_metadata or {}).get("request_fingerprint", ""))) == 64


def main() -> None:
    _assert_postgresql()
    identical_retry_probe()
    contradictory_retry_probe()
    print("PostgreSQL full-request idempotency probes passed")


if __name__ == "__main__":
    main()
