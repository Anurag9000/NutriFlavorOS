"""Transactional household inventory, leftovers, shopping reconciliation, and batch prep."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import (
    DBHousehold,
    DBHouseholdMember,
    DBInventoryEvent,
    DBLeftoverBatch,
    DBMealPlan,
    DBPantryItem,
    DBRecipe,
    DBUser,
)
from backend.domain.ingredients import canonicalize_ingredient_name
from backend.domain.inventory import (
    BatchPrepTask,
    HouseholdCreate,
    HouseholdMemberCreate,
    InventoryEventType,
    InventoryMutation,
    LeftoverConsume,
    LeftoverCreate,
    PantryItemCreate,
    ReconciledShoppingItem,
)
from backend.domain.quantities import normalize_quantity_values
from backend.models import PlanResponse


_EPSILON = 1e-9


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Resource not found")


def _idempotency_conflict(message: str = "Idempotency key was already used for a different request") -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": "idempotency_key_reused", "message": message},
    )


def require_household_owner(db: Session, household_id: str, user_id: str) -> DBHousehold:
    value = (
        db.query(DBHousehold)
        .filter(DBHousehold.id == household_id, DBHousehold.owner_user_id == user_id)
        .first()
    )
    if value is None:
        raise _not_found()
    return value


def list_households(db: Session, user_id: str) -> List[DBHousehold]:
    return (
        db.query(DBHousehold)
        .filter(DBHousehold.owner_user_id == user_id)
        .order_by(DBHousehold.created_at, DBHousehold.id)
        .all()
    )


def create_household(db: Session, owner: DBUser, payload: HouseholdCreate) -> DBHousehold:
    now = utcnow()
    value = DBHousehold(
        id=str(uuid4()),
        owner_user_id=owner.id,
        name=payload.name.strip(),
        timezone=payload.timezone.strip(),
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(value)
    db.flush()
    db.add(
        DBHouseholdMember(
            household_id=value.id,
            display_name=owner.name or owner.id,
            linked_user_id=owner.id,
            servings_multiplier=1.0,
            allergies=list(owner.allergies or []),
            dietary_restrictions=list(owner.dietary_restrictions or []),
            disliked_ingredients=list(owner.disliked_ingredients or []),
            active=True,
            created_at=now,
        )
    )
    db.commit()
    db.refresh(value)
    return value


def add_household_member(
    db: Session,
    household: DBHousehold,
    payload: HouseholdMemberCreate,
    owner_user_id: str,
) -> DBHouseholdMember:
    if payload.linked_user_id not in {None, owner_user_id}:
        raise HTTPException(
            status_code=422,
            detail="Linking another account requires an accepted invitation",
        )

    def clean(values: Iterable[str]) -> List[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})

    value = DBHouseholdMember(
        household_id=household.id,
        display_name=payload.display_name.strip(),
        linked_user_id=payload.linked_user_id,
        servings_multiplier=payload.servings_multiplier,
        allergies=clean(payload.allergies),
        dietary_restrictions=clean(payload.dietary_restrictions),
        disliked_ingredients=clean(payload.disliked_ingredients),
        active=payload.active,
        created_at=utcnow(),
    )
    household.version += 1
    household.updated_at = utcnow()
    db.add_all([value, household])
    db.commit()
    db.refresh(value)
    return value


def _event_by_key(
    db: Session, household_id: str, key: Optional[str]
) -> Optional[DBInventoryEvent]:
    if not key:
        return None
    return (
        db.query(DBInventoryEvent)
        .filter(
            DBInventoryEvent.household_id == household_id,
            DBInventoryEvent.idempotency_key == key,
        )
        .first()
    )


def _event(
    db: Session,
    *,
    household_id: str,
    event_type: InventoryEventType,
    qmin: float,
    qmax: float,
    unit: str,
    pantry_item_id: Optional[int] = None,
    leftover_id: Optional[int] = None,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> None:
    db.add(
        DBInventoryEvent(
            household_id=household_id,
            pantry_item_id=pantry_item_id,
            leftover_id=leftover_id,
            event_type=event_type.value,
            quantity_min=qmin,
            quantity_max=qmax,
            unit=unit,
            reason=reason,
            event_metadata=dict(metadata or {}),
            idempotency_key=key,
            created_at=utcnow(),
        )
    )


def _same_number(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= _EPSILON


def _resolve_prior_pantry_event(
    db: Session,
    *,
    household_id: str,
    key: Optional[str],
    event_type: InventoryEventType,
    qmin: float,
    qmax: float,
    unit: str,
    item_id: Optional[int] = None,
    canonical_name: Optional[str] = None,
) -> Optional[DBPantryItem]:
    prior = _event_by_key(db, household_id, key)
    if prior is None:
        return None
    if (
        prior.event_type != event_type.value
        or prior.pantry_item_id is None
        or (item_id is not None and prior.pantry_item_id != item_id)
        or prior.unit != unit
        or not _same_number(prior.quantity_min, qmin)
        or not _same_number(prior.quantity_max, qmax)
    ):
        raise _idempotency_conflict()
    value = db.get(DBPantryItem, prior.pantry_item_id)
    if value is None:
        raise _idempotency_conflict("The original idempotent result is no longer available")
    if canonical_name is not None and value.canonical_name != canonical_name:
        raise _idempotency_conflict()
    return value


def _resolve_prior_leftover_event(
    db: Session,
    *,
    household_id: str,
    key: Optional[str],
    event_type: InventoryEventType,
    portions: float,
    leftover_id: Optional[int] = None,
    recipe_id: Optional[str] = None,
) -> Optional[DBLeftoverBatch]:
    prior = _event_by_key(db, household_id, key)
    if prior is None:
        return None
    if (
        prior.event_type != event_type.value
        or prior.leftover_id is None
        or (leftover_id is not None and prior.leftover_id != leftover_id)
        or prior.unit != "portion"
        or not _same_number(prior.quantity_min, portions)
        or not _same_number(prior.quantity_max, portions)
    ):
        raise _idempotency_conflict()
    value = db.get(DBLeftoverBatch, prior.leftover_id)
    if value is None:
        raise _idempotency_conflict("The original idempotent result is no longer available")
    if recipe_id is not None and value.recipe_id != recipe_id:
        raise _idempotency_conflict()
    return value


def add_pantry_item(
    db: Session, household: DBHousehold, payload: PantryItemCreate
) -> DBPantryItem:
    name = canonicalize_ingredient_name(payload.ingredient_name)
    if not name:
        raise HTTPException(
            status_code=422, detail="ingredient_name could not be normalized"
        )
    qmin, qmax, unit = normalize_quantity_values(
        payload.quantity.quantity_min,
        payload.quantity.quantity_max,
        payload.quantity.unit,
    )
    prior = _resolve_prior_pantry_event(
        db,
        household_id=household.id,
        key=payload.idempotency_key,
        event_type=InventoryEventType.PURCHASE,
        qmin=qmin,
        qmax=qmax,
        unit=unit,
        canonical_name=name,
    )
    if prior is not None:
        return prior

    now = utcnow()
    value = DBPantryItem(
        household_id=household.id,
        canonical_name=name,
        display_name=(payload.display_name or payload.ingredient_name).strip(),
        quantity_min=qmin,
        quantity_max=qmax,
        unit=unit,
        expires_at=payload.expires_at,
        opened_at=payload.opened_at,
        source=payload.source,
        item_metadata=dict(payload.metadata),
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(value)
    db.flush()
    _event(
        db,
        household_id=household.id,
        pantry_item_id=value.id,
        event_type=InventoryEventType.PURCHASE,
        qmin=qmin,
        qmax=qmax,
        unit=unit,
        metadata={
            "source": payload.source,
            "canonical_name": name,
            "result_version": 1,
        },
        key=payload.idempotency_key,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = _resolve_prior_pantry_event(
            db,
            household_id=household.id,
            key=payload.idempotency_key,
            event_type=InventoryEventType.PURCHASE,
            qmin=qmin,
            qmax=qmax,
            unit=unit,
            canonical_name=name,
        )
        if prior is not None:
            return prior
        raise
    db.refresh(value)
    return value


def list_pantry_items(
    db: Session, household_id: str, *, include_empty: bool = False
) -> List[DBPantryItem]:
    query = db.query(DBPantryItem).filter(DBPantryItem.household_id == household_id)
    if not include_empty:
        query = query.filter(DBPantryItem.quantity_max > 0)
    return query.order_by(
        DBPantryItem.expires_at.is_(None),
        DBPantryItem.expires_at,
        DBPantryItem.created_at,
        DBPantryItem.id,
    ).all()


def _check_version(actual: int, expected: Optional[int]) -> None:
    if expected is not None and actual != expected:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_version",
                "message": "Inventory item was modified",
                "current_version": actual,
            },
        )


def consume_pantry_item(
    db: Session,
    household: DBHousehold,
    item_id: int,
    payload: InventoryMutation,
    *,
    event_type: InventoryEventType = InventoryEventType.CONSUME,
) -> DBPantryItem:
    qmin, qmax, unit = normalize_quantity_values(
        payload.quantity.quantity_min,
        payload.quantity.quantity_max,
        payload.quantity.unit,
    )
    prior = _resolve_prior_pantry_event(
        db,
        household_id=household.id,
        key=payload.idempotency_key,
        event_type=event_type,
        qmin=qmin,
        qmax=qmax,
        unit=unit,
        item_id=item_id,
    )
    if prior is not None:
        return prior

    value = (
        db.query(DBPantryItem)
        .filter(
            DBPantryItem.id == item_id,
            DBPantryItem.household_id == household.id,
        )
        .with_for_update()
        .first()
    )
    if value is None:
        raise _not_found()

    # A concurrent request may have committed while this transaction waited for
    # the row lock. Re-check the ledger after the lock is acquired.
    prior = _resolve_prior_pantry_event(
        db,
        household_id=household.id,
        key=payload.idempotency_key,
        event_type=event_type,
        qmin=qmin,
        qmax=qmax,
        unit=unit,
        item_id=item_id,
    )
    if prior is not None:
        return prior

    _check_version(value.version, payload.expected_version)
    if unit != value.unit:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "incompatible_unit",
                "message": f"Cannot subtract {unit} from {value.unit}",
            },
        )
    if qmax > value.quantity_max + _EPSILON:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "insufficient_inventory",
                "available_max": value.quantity_max,
                "requested_max": qmax,
                "unit": unit,
            },
        )

    value.quantity_min = max(0.0, value.quantity_min - qmax)
    value.quantity_max = max(0.0, value.quantity_max - qmin)
    value.version += 1
    value.updated_at = utcnow()
    db.add(value)
    _event(
        db,
        household_id=household.id,
        pantry_item_id=value.id,
        event_type=event_type,
        qmin=qmin,
        qmax=qmax,
        unit=unit,
        reason=payload.reason,
        metadata={
            "result_version": value.version,
            "result_quantity_min": value.quantity_min,
            "result_quantity_max": value.quantity_max,
        },
        key=payload.idempotency_key,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = _resolve_prior_pantry_event(
            db,
            household_id=household.id,
            key=payload.idempotency_key,
            event_type=event_type,
            qmin=qmin,
            qmax=qmax,
            unit=unit,
            item_id=item_id,
        )
        if prior is not None:
            return prior
        raise
    db.refresh(value)
    return value


def set_pantry_quantity(
    db: Session,
    household: DBHousehold,
    item_id: int,
    payload: InventoryMutation,
) -> DBPantryItem:
    qmin, qmax, unit = normalize_quantity_values(
        payload.quantity.quantity_min,
        payload.quantity.quantity_max,
        payload.quantity.unit,
    )
    prior = _resolve_prior_pantry_event(
        db,
        household_id=household.id,
        key=payload.idempotency_key,
        event_type=InventoryEventType.ADJUST,
        qmin=qmin,
        qmax=qmax,
        unit=unit,
        item_id=item_id,
    )
    if prior is not None:
        return prior

    value = (
        db.query(DBPantryItem)
        .filter(
            DBPantryItem.id == item_id,
            DBPantryItem.household_id == household.id,
        )
        .with_for_update()
        .first()
    )
    if value is None:
        raise _not_found()

    prior = _resolve_prior_pantry_event(
        db,
        household_id=household.id,
        key=payload.idempotency_key,
        event_type=InventoryEventType.ADJUST,
        qmin=qmin,
        qmax=qmax,
        unit=unit,
        item_id=item_id,
    )
    if prior is not None:
        return prior

    _check_version(value.version, payload.expected_version)
    value.quantity_min = qmin
    value.quantity_max = qmax
    value.unit = unit
    value.version += 1
    value.updated_at = utcnow()
    db.add(value)
    _event(
        db,
        household_id=household.id,
        pantry_item_id=value.id,
        event_type=InventoryEventType.ADJUST,
        qmin=qmin,
        qmax=qmax,
        unit=unit,
        reason=payload.reason,
        metadata={
            "absolute_quantity": True,
            "result_version": value.version,
            "result_quantity_min": value.quantity_min,
            "result_quantity_max": value.quantity_max,
        },
        key=payload.idempotency_key,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = _resolve_prior_pantry_event(
            db,
            household_id=household.id,
            key=payload.idempotency_key,
            event_type=InventoryEventType.ADJUST,
            qmin=qmin,
            qmax=qmax,
            unit=unit,
            item_id=item_id,
        )
        if prior is not None:
            return prior
        raise
    db.refresh(value)
    return value


def create_leftover(
    db: Session, household: DBHousehold, payload: LeftoverCreate
) -> DBLeftoverBatch:
    prior = _resolve_prior_leftover_event(
        db,
        household_id=household.id,
        key=payload.idempotency_key,
        event_type=InventoryEventType.LEFTOVER_CREATE,
        portions=payload.portions_available,
        recipe_id=payload.recipe_id,
    )
    if prior is not None:
        return prior
    if db.get(DBRecipe, payload.recipe_id) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if payload.source_plan_id is not None:
        source_plan = (
            db.query(DBMealPlan)
            .filter(
                DBMealPlan.id == payload.source_plan_id,
                DBMealPlan.user_id == household.owner_user_id,
            )
            .first()
        )
        if source_plan is None:
            raise HTTPException(status_code=404, detail="Source meal plan not found")

    now = utcnow()
    value = DBLeftoverBatch(
        household_id=household.id,
        recipe_id=payload.recipe_id,
        source_plan_id=payload.source_plan_id,
        portions_available=payload.portions_available,
        cooked_at=payload.cooked_at,
        expires_at=payload.expires_at,
        frozen=payload.frozen,
        notes=payload.notes,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(value)
    db.flush()
    _event(
        db,
        household_id=household.id,
        leftover_id=value.id,
        event_type=InventoryEventType.LEFTOVER_CREATE,
        qmin=payload.portions_available,
        qmax=payload.portions_available,
        unit="portion",
        metadata={"recipe_id": payload.recipe_id, "result_version": 1},
        key=payload.idempotency_key,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = _resolve_prior_leftover_event(
            db,
            household_id=household.id,
            key=payload.idempotency_key,
            event_type=InventoryEventType.LEFTOVER_CREATE,
            portions=payload.portions_available,
            recipe_id=payload.recipe_id,
        )
        if prior is not None:
            return prior
        raise
    db.refresh(value)
    return value


def consume_leftover(
    db: Session,
    household: DBHousehold,
    leftover_id: int,
    payload: LeftoverConsume,
) -> DBLeftoverBatch:
    prior = _resolve_prior_leftover_event(
        db,
        household_id=household.id,
        key=payload.idempotency_key,
        event_type=InventoryEventType.LEFTOVER_CONSUME,
        portions=payload.portions,
        leftover_id=leftover_id,
    )
    if prior is not None:
        return prior

    value = (
        db.query(DBLeftoverBatch)
        .filter(
            DBLeftoverBatch.id == leftover_id,
            DBLeftoverBatch.household_id == household.id,
        )
        .with_for_update()
        .first()
    )
    if value is None:
        raise _not_found()

    prior = _resolve_prior_leftover_event(
        db,
        household_id=household.id,
        key=payload.idempotency_key,
        event_type=InventoryEventType.LEFTOVER_CONSUME,
        portions=payload.portions,
        leftover_id=leftover_id,
    )
    if prior is not None:
        return prior

    _check_version(value.version, payload.expected_version)
    if payload.portions > value.portions_available + _EPSILON:
        raise HTTPException(
            status_code=409,
            detail="Requested portions exceed available leftovers",
        )

    value.portions_available = max(
        0.0, value.portions_available - payload.portions
    )
    value.version += 1
    value.updated_at = utcnow()
    db.add(value)
    _event(
        db,
        household_id=household.id,
        leftover_id=value.id,
        event_type=InventoryEventType.LEFTOVER_CONSUME,
        qmin=payload.portions,
        qmax=payload.portions,
        unit="portion",
        metadata={
            "result_version": value.version,
            "result_portions_available": value.portions_available,
        },
        key=payload.idempotency_key,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = _resolve_prior_leftover_event(
            db,
            household_id=household.id,
            key=payload.idempotency_key,
            event_type=InventoryEventType.LEFTOVER_CONSUME,
            portions=payload.portions,
            leftover_id=leftover_id,
        )
        if prior is not None:
            return prior
        raise
    db.refresh(value)
    return value


def list_leftovers(
    db: Session, household_id: str, *, include_empty: bool = False
) -> List[DBLeftoverBatch]:
    query = db.query(DBLeftoverBatch).filter(
        DBLeftoverBatch.household_id == household_id
    )
    if not include_empty:
        query = query.filter(DBLeftoverBatch.portions_available > 0)
    return query.order_by(
        DBLeftoverBatch.expires_at.is_(None),
        DBLeftoverBatch.expires_at,
        DBLeftoverBatch.cooked_at,
        DBLeftoverBatch.id,
    ).all()


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def _pantry_totals(
    items: Iterable[DBPantryItem], now: datetime
) -> Dict[Tuple[str, str], Dict[str, float]]:
    totals: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(
        lambda: {"min": 0.0, "max": 0.0, "expiring_max": 0.0}
    )
    cutoff = now + timedelta(days=3)
    for item in items:
        expiry = _as_utc(item.expires_at) if item.expires_at else None
        if expiry and expiry <= now:
            continue
        key = (item.canonical_name, item.unit)
        totals[key]["min"] += float(item.quantity_min)
        totals[key]["max"] += float(item.quantity_max)
        if expiry and expiry <= cutoff:
            totals[key]["expiring_max"] += float(item.quantity_max)
    return totals


def reconcile_shopping_list(
    plan: PlanResponse,
    pantry_items: Iterable[DBPantryItem],
    *,
    now: Optional[datetime] = None,
) -> List[ReconciledShoppingItem]:
    pantry = _pantry_totals(pantry_items, now or utcnow())
    required: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {
            "min": 0.0,
            "max": 0.0,
            "display": "",
            "ids": set(),
            "notes": [],
        }
    )
    for category in (plan.shopping_list or {}).values():
        if not isinstance(category, dict):
            continue
        for fallback, item in category.items():
            if not isinstance(item, dict):
                continue
            name = canonicalize_ingredient_name(str(fallback))
            display = str(item.get("display_name") or fallback)
            ids = {str(value) for value in item.get("source_recipe_ids", [])}
            quantities = item.get("quantities", [])
            if not quantities:
                key = (name, "unquantified")
                required[key]["display"] = display
                required[key]["ids"].update(ids)
                required[key]["notes"].append(
                    "No normalized quantity was available"
                )
                continue
            for quantity in quantities:
                if not isinstance(quantity, dict):
                    continue
                unit = str(quantity.get("unit") or "unquantified")
                key = (name, unit)
                required[key]["min"] += float(
                    quantity.get("quantity_min", 0) or 0
                )
                required[key]["max"] += float(
                    quantity.get("quantity_max", 0) or 0
                )
                required[key]["display"] = display
                required[key]["ids"].update(ids)

    result: List[ReconciledShoppingItem] = []
    for (name, unit), need in sorted(required.items()):
        available = pantry.get(
            (name, unit), {"min": 0.0, "max": 0.0, "expiring_max": 0.0}
        )
        if unit == "unquantified":
            buy_min = buy_max = 0.0
            coverage = "unquantified"
        else:
            buy_min = max(0.0, need["min"] - available["max"])
            buy_max = max(0.0, need["max"] - available["min"])
            coverage = (
                "covered"
                if buy_max <= _EPSILON
                else "partial"
                if available["max"] > 0
                else "not_covered"
            )
        notes = list(dict.fromkeys(need["notes"]))
        if available["expiring_max"] > 0:
            notes.append("Use expiring pantry stock first")
        result.append(
            ReconciledShoppingItem(
                canonical_name=name,
                display_name=need["display"] or name,
                unit=unit,
                required_min=round(need["min"], 6),
                required_max=round(need["max"], 6),
                pantry_min=round(available["min"], 6),
                pantry_max=round(available["max"], 6),
                buy_min=round(buy_min, 6),
                buy_max=round(buy_max, 6),
                coverage_status=coverage,
                expiring_quantity_max=round(available["expiring_max"], 6),
                source_recipe_ids=sorted(need["ids"]),
                notes=notes,
            )
        )
    return result


def build_batch_prep_tasks(plan: PlanResponse) -> List[BatchPrepTask]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for day in plan.days:
        for slot, recipe in day.meals.items():
            entry = grouped.setdefault(
                recipe.id,
                {
                    "name": recipe.name,
                    "portions": 0.0,
                    "first": day.day,
                    "count": 0,
                    "slots": [],
                },
            )
            entry["portions"] += float(day.portions.get(slot, 1.0))
            entry["first"] = min(entry["first"], day.day)
            entry["count"] += 1
            entry["slots"].append(f"day_{day.day}:{slot}")
    tasks = [
        BatchPrepTask(
            recipe_id=identifier,
            recipe_name=value["name"],
            total_portions=round(value["portions"], 3),
            first_day=int(value["first"]),
            scheduled_day=max(1, int(value["first"]) - 1),
            occurrences=value["count"],
            meal_slots=value["slots"],
        )
        for identifier, value in grouped.items()
        if value["count"] >= 2
    ]
    return sorted(
        tasks, key=lambda item: (item.scheduled_day, item.recipe_name.lower(), item.recipe_id)
    )
