"""Expiry-ordered, uncertainty-aware pantry stock reservations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database import (
    DBHousehold,
    DBInventoryEvent,
    DBMealPlan,
    DBPantryItem,
    DBStockReservation,
)
from backend.domain.household_access import (
    ReservationMutation,
    ReservationStatus,
)
from backend.domain.inventory import InventoryEventType, ReconciledShoppingItem


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def expire_reservations(db: Session, household_id: str | None = None) -> int:
    query = db.query(DBStockReservation).filter(
        DBStockReservation.status == ReservationStatus.ACTIVE.value,
        DBStockReservation.expires_at <= utcnow(),
    )
    if household_id:
        query = query.filter(DBStockReservation.household_id == household_id)
    values = query.with_for_update().all()
    now = utcnow()
    for value in values:
        value.status = ReservationStatus.EXPIRED.value
        value.version += 1
        value.updated_at = now
        db.add(value)
    if values:
        db.commit()
    return len(values)


def _active_reserved_by_item(db: Session, household_id: str) -> Dict[int, Tuple[float, float]]:
    expire_reservations(db, household_id)
    rows = (
        db.query(DBStockReservation)
        .filter(
            DBStockReservation.household_id == household_id,
            DBStockReservation.status == ReservationStatus.ACTIVE.value,
        )
        .all()
    )
    result: Dict[int, Tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
    for row in rows:
        if row.pantry_item_id is None:
            continue
        old_min, old_max = result[row.pantry_item_id]
        result[row.pantry_item_id] = (
            old_min + float(row.quantity_min),
            old_max + float(row.quantity_max),
        )
    return result


def usable_pantry_intervals(
    db: Session, household_id: str
) -> Dict[Tuple[str, str], Dict[str, float]]:
    now = utcnow()
    reserved = _active_reserved_by_item(db, household_id)
    rows = (
        db.query(DBPantryItem)
        .filter(
            DBPantryItem.household_id == household_id,
            DBPantryItem.quantity_max > 0,
        )
        .all()
    )
    result: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(
        lambda: {"min": 0.0, "max": 0.0, "lots": 0.0}
    )
    for row in rows:
        if row.expires_at is not None and _as_utc(row.expires_at) <= now:
            continue
        reserved_min, reserved_max = reserved.get(row.id, (0.0, 0.0))
        available_min = max(0.0, float(row.quantity_min) - reserved_max)
        available_max = max(0.0, float(row.quantity_max) - reserved_min)
        if available_max <= 1e-12:
            continue
        key = (row.canonical_name, row.unit)
        result[key]["min"] += available_min
        result[key]["max"] += available_max
        result[key]["lots"] += 1.0
    return dict(result)


def ingredient_availability_score(
    recipe_ingredient_names: Iterable[str],
    pantry_intervals: Dict[Tuple[str, str], Dict[str, float]],
) -> float:
    names = {value for value in recipe_ingredient_names if value}
    if not names:
        return 0.0
    available_names = {
        name
        for (name, _unit), values in pantry_intervals.items()
        if values.get("max", 0.0) > 0
    }
    return len(names & available_names) / len(names)


def create_plan_reservations(
    db: Session,
    *,
    household: DBHousehold,
    plan: DBMealPlan,
    shopping: Iterable[ReconciledShoppingItem],
    reservation_hours: int,
) -> List[DBStockReservation]:
    if plan.household_id != household.id:
        raise HTTPException(status_code=409, detail="Plan is not associated with this household")
    expire_reservations(db, household.id)
    if (
        db.query(DBStockReservation)
        .filter(
            DBStockReservation.plan_id == plan.id,
            DBStockReservation.status == ReservationStatus.ACTIVE.value,
        )
        .count()
        > 0
    ):
        return (
            db.query(DBStockReservation)
            .filter(
                DBStockReservation.plan_id == plan.id,
                DBStockReservation.status == ReservationStatus.ACTIVE.value,
            )
            .order_by(DBStockReservation.id)
            .all()
        )

    reserved = _active_reserved_by_item(db, household.id)
    expires_at = utcnow() + timedelta(hours=reservation_hours)
    created: List[DBStockReservation] = []

    for needed in shopping:
        if needed.unit == "unquantified" or needed.required_max <= 0:
            continue
        remaining_min = max(0.0, needed.required_min)
        remaining_max = max(0.0, needed.required_max)
        lots = (
            db.query(DBPantryItem)
            .filter(
                DBPantryItem.household_id == household.id,
                DBPantryItem.canonical_name == needed.canonical_name,
                DBPantryItem.unit == needed.unit,
                DBPantryItem.quantity_max > 0,
            )
            .order_by(
                DBPantryItem.expires_at.is_(None),
                DBPantryItem.expires_at,
                DBPantryItem.opened_at.is_(None),
                DBPantryItem.opened_at,
                DBPantryItem.created_at,
                DBPantryItem.id,
            )
            .with_for_update()
            .all()
        )
        for lot in lots:
            if lot.expires_at is not None and _as_utc(lot.expires_at) <= utcnow():
                continue
            held_min, held_max = reserved.get(lot.id, (0.0, 0.0))
            available_min = max(0.0, float(lot.quantity_min) - held_max)
            available_max = max(0.0, float(lot.quantity_max) - held_min)
            if available_max <= 1e-12 or remaining_max <= 1e-12:
                continue

            allocate_max = min(available_max, remaining_max)
            allocate_min = min(available_min, remaining_min, allocate_max)
            value = DBStockReservation(
                household_id=household.id,
                pantry_item_id=lot.id,
                plan_id=plan.id,
                canonical_name=needed.canonical_name,
                quantity_min=allocate_min,
                quantity_max=allocate_max,
                unit=needed.unit,
                status=ReservationStatus.ACTIVE.value,
                expires_at=expires_at,
                version=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(value)
            created.append(value)
            reserved[lot.id] = (held_min + allocate_min, held_max + allocate_max)
            remaining_min = max(0.0, remaining_min - allocate_min)
            remaining_max = max(0.0, remaining_max - allocate_max)

    db.commit()
    for value in created:
        db.refresh(value)
    return created


def list_reservations(
    db: Session,
    household_id: str,
    *,
    include_closed: bool = False,
) -> List[DBStockReservation]:
    expire_reservations(db, household_id)
    query = db.query(DBStockReservation).filter(
        DBStockReservation.household_id == household_id
    )
    if not include_closed:
        query = query.filter(DBStockReservation.status == ReservationStatus.ACTIVE.value)
    return query.order_by(
        DBStockReservation.expires_at,
        DBStockReservation.created_at,
        DBStockReservation.id,
    ).all()


def release_plan_reservations(
    db: Session,
    household_id: str,
    plan_id: int,
    payload: ReservationMutation,
) -> List[DBStockReservation]:
    rows = (
        db.query(DBStockReservation)
        .filter(
            DBStockReservation.household_id == household_id,
            DBStockReservation.plan_id == plan_id,
            DBStockReservation.status == ReservationStatus.ACTIVE.value,
        )
        .with_for_update()
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No active reservations found")
    now = utcnow()
    for row in rows:
        if payload.expected_version is not None and row.version != payload.expected_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "stale_version",
                    "message": "Reservation was modified",
                    "reservation_id": row.id,
                    "current_version": row.version,
                },
            )
        row.status = ReservationStatus.RELEASED.value
        row.version += 1
        row.updated_at = now
        db.add(row)
    db.commit()
    return rows


def commit_plan_reservations(
    db: Session,
    household_id: str,
    plan_id: int,
    payload: ReservationMutation,
) -> List[DBStockReservation]:
    rows = (
        db.query(DBStockReservation)
        .filter(
            DBStockReservation.household_id == household_id,
            DBStockReservation.plan_id == plan_id,
            DBStockReservation.status == ReservationStatus.ACTIVE.value,
        )
        .order_by(DBStockReservation.id)
        .with_for_update()
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No active reservations found")

    now = utcnow()
    for row in rows:
        if payload.expected_version is not None and row.version != payload.expected_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "stale_version",
                    "message": "Reservation was modified",
                    "reservation_id": row.id,
                    "current_version": row.version,
                },
            )
        if _as_utc(row.expires_at) <= now:
            row.status = ReservationStatus.EXPIRED.value
            row.version += 1
            row.updated_at = now
            db.add(row)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "reservation_expired",
                    "message": "Reservation expired before it was committed",
                    "reservation_id": row.id,
                },
            )
        item = (
            db.query(DBPantryItem)
            .filter(
                DBPantryItem.id == row.pantry_item_id,
                DBPantryItem.household_id == household_id,
            )
            .with_for_update()
            .first()
        )
        if item is None or item.unit != row.unit:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "reserved_stock_unavailable",
                    "message": "Reserved pantry lot no longer exists or changed unit",
                    "reservation_id": row.id,
                },
            )
        if float(item.quantity_max) + 1e-9 < float(row.quantity_max):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "reserved_stock_insufficient",
                    "message": "Reserved pantry lot no longer contains the reserved amount",
                    "reservation_id": row.id,
                },
            )

        item.quantity_min = max(0.0, float(item.quantity_min) - float(row.quantity_max))
        item.quantity_max = max(0.0, float(item.quantity_max) - float(row.quantity_min))
        item.version += 1
        item.updated_at = now
        row.status = ReservationStatus.CONSUMED.value
        row.version += 1
        row.updated_at = now
        db.add_all([item, row])
        db.add(
            DBInventoryEvent(
                household_id=household_id,
                pantry_item_id=item.id,
                leftover_id=None,
                event_type=InventoryEventType.RESERVATION_COMMIT.value,
                quantity_min=row.quantity_min,
                quantity_max=row.quantity_max,
                unit=row.unit,
                reason=payload.reason or f"Committed meal-plan reservation {plan_id}",
                event_metadata={"plan_id": plan_id, "reservation_id": row.id},
                idempotency_key=None,
                created_at=now,
            )
        )
    db.commit()
    return rows
