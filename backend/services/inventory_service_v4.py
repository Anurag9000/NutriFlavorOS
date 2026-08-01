"""Household inventory extensions for roles, targets, and reviewed storage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import (
    DBHousehold,
    DBHouseholdMember,
    DBLeftoverBatch,
    DBMealPlan,
    DBRecipe,
    DBStoragePolicy,
    DBUser,
)
from backend.domain.inventory import (
    BatchPrepTask,
    HouseholdCreate,
    HouseholdMemberCreate,
    InventoryEventType,
    LeftoverCreate,
)
from backend.evidence_history_models import DBLeftoverStoragePolicyEvidence
from backend.models import PlanResponse
from backend.services.evidence_history_service import active_reviewed_storage_policy
from backend.services.inventory_service import (
    _event,
    _resolve_prior_leftover_event,
    add_pantry_item,
    consume_leftover,
    consume_pantry_item,
    list_leftovers,
    list_pantry_items,
    reconcile_shopping_list,
    set_pantry_quantity,
    utcnow,
)


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def create_household(
    db: Session, owner: DBUser, payload: HouseholdCreate
) -> DBHousehold:
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
            role="owner",
            servings_multiplier=1.0,
            allergies=list(owner.allergies or []),
            dietary_restrictions=list(owner.dietary_restrictions or []),
            disliked_ingredients=list(owner.disliked_ingredients or []),
            target_calories=owner.target_calories,
            target_protein_g=owner.target_protein_g,
            target_carbs_g=owner.target_carbs_g,
            target_fat_g=owner.target_fat_g,
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
    locked_household = (
        db.query(DBHousehold)
        .filter(DBHousehold.id == household.id)
        .with_for_update()
        .first()
    )
    if locked_household is None or locked_household.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Resource not found")
    if payload.linked_user_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Linking an account requires an accepted invitation",
        )

    def clean(values: Iterable[str]) -> List[str]:
        return sorted({item.strip().lower() for item in values if item.strip()})

    value = DBHouseholdMember(
        household_id=locked_household.id,
        display_name=payload.display_name.strip(),
        linked_user_id=None,
        role=payload.role.value,
        servings_multiplier=payload.servings_multiplier,
        allergies=clean(payload.allergies),
        dietary_restrictions=clean(payload.dietary_restrictions),
        disliked_ingredients=clean(payload.disliked_ingredients),
        target_calories=payload.target_calories,
        target_protein_g=payload.target_protein_g,
        target_carbs_g=payload.target_carbs_g,
        target_fat_g=payload.target_fat_g,
        active=payload.active,
        created_at=utcnow(),
    )
    locked_household.version += 1
    locked_household.updated_at = utcnow()
    db.add_all([value, locked_household])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "household_member_conflict",
                "message": "Household member could not be created because the state changed",
            },
        ) from exc
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
                DBMealPlan.household_id == household.id,
            )
            .first()
        )
        if source_plan is None:
            raise HTTPException(
                status_code=404, detail="Source household meal plan not found"
            )

    policy = None
    expires_at = payload.expires_at
    expected_storage_state = "frozen" if payload.frozen else "refrigerated"
    if payload.storage_policy_key:
        policy = active_reviewed_storage_policy(db, payload.storage_policy_key)
        if policy.storage_state != expected_storage_state:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "storage_policy_state_mismatch",
                    "message": (
                        f"Policy requires {policy.storage_state} storage but the "
                        f"leftover is marked {expected_storage_state}"
                    ),
                },
            )
        if policy.duration_max_hours is not None:
            policy_limit = payload.cooked_at + timedelta(
                hours=float(policy.duration_max_hours)
            )
            if expires_at is not None and _as_utc(expires_at) > _as_utc(policy_limit):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "expiry_exceeds_reviewed_policy",
                        "message": "Explicit expiry exceeds the selected reviewed policy",
                    },
                )
            # Quality guidance is not converted into a safety-expiry timestamp.
            if expires_at is None and policy.safety_scope != "quality_guidance":
                expires_at = policy_limit

    now = utcnow()
    notes = payload.notes
    if policy is not None:
        limit_text = (
            f" at or below {policy.maximum_temperature_c}°C"
            if policy.maximum_temperature_c is not None
            else ""
        )
        suffix = (
            f"Storage policy {policy.policy_key} version {policy.policy_version} "
            f"assumes {policy.storage_state} storage{limit_text}; inspect food, "
            "cold-chain history, packaging, power loss, and vulnerable-person "
            "considerations."
        )
        if policy.safety_scope == "quality_guidance":
            suffix += " The duration is quality guidance and is not a safety expiry."
        notes = f"{notes}\n{suffix}".strip() if notes else suffix

    value = DBLeftoverBatch(
        household_id=household.id,
        recipe_id=payload.recipe_id,
        source_plan_id=payload.source_plan_id,
        portions_available=payload.portions_available,
        cooked_at=payload.cooked_at,
        expires_at=expires_at,
        frozen=payload.frozen,
        notes=notes,
        storage_policy_key=payload.storage_policy_key,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(value)
    db.flush()
    if policy is not None:
        db.add(
            DBLeftoverStoragePolicyEvidence(
                leftover_id=value.id,
                storage_policy_version_id=policy.id,
                linked_at=now,
            )
        )
        db.flush()
    _event(
        db,
        household_id=household.id,
        leftover_id=value.id,
        event_type=InventoryEventType.LEFTOVER_CREATE,
        qmin=payload.portions_available,
        qmax=payload.portions_available,
        unit="portion",
        metadata={
            "storage_policy_key": payload.storage_policy_key,
            "storage_policy_version_id": policy.id if policy is not None else None,
            "storage_policy_version": (
                policy.policy_version if policy is not None else None
            ),
            "storage_policy_content_hash": (
                policy.content_hash if policy is not None else None
            ),
            "storage_state": expected_storage_state,
            "recipe_id": payload.recipe_id,
            "result_version": 1,
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
            event_type=InventoryEventType.LEFTOVER_CREATE,
            portions=payload.portions_available,
            recipe_id=payload.recipe_id,
        )
        if prior is not None:
            return prior
        raise
    db.refresh(value)
    return value


def build_batch_prep_tasks(
    plan: PlanResponse,
    storage_policies: Iterable[DBStoragePolicy] = (),
) -> List[BatchPrepTask]:
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
    policy_keys = sorted(
        {
            value.policy_key
            for value in storage_policies
            if value.active and value.food_category == "cooked leftovers"
        }
    )
    tasks = [
        BatchPrepTask(
            recipe_id=identifier,
            recipe_name=value["name"],
            total_portions=round(value["portions"], 3),
            first_day=int(value["first"]),
            scheduled_day=max(1, int(value["first"]) - 1),
            occurrences=value["count"],
            meal_slots=value["slots"],
            applicable_storage_policies=policy_keys,
        )
        for identifier, value in grouped.items()
        if value["count"] >= 2
    ]
    return sorted(
        tasks,
        key=lambda item: (item.scheduled_day, item.recipe_name.lower(), item.recipe_id),
    )
