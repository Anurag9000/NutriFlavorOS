"""Fourth-slice household inventory extensions.

This module keeps the stable transactional pantry implementation and adds role,
target, reviewed-storage, and household-plan semantics without duplicating the
core lot arithmetic.
"""
from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict, Iterable, List
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.database import DBHousehold, DBHouseholdMember, DBLeftoverBatch, DBMealPlan, DBRecipe, DBStoragePolicy, DBUser
from backend.domain.inventory import BatchPrepTask, HouseholdCreate, HouseholdMemberCreate, InventoryEventType, LeftoverCreate
from backend.models import PlanResponse
from backend.services.inventory_service import (
    _event, _event_by_key, add_pantry_item, consume_leftover, consume_pantry_item,
    list_leftovers, list_pantry_items, reconcile_shopping_list, set_pantry_quantity,
    utcnow,
)


def create_household(db: Session, owner: DBUser, payload: HouseholdCreate) -> DBHousehold:
    now=utcnow(); value=DBHousehold(id=str(uuid4()),owner_user_id=owner.id,name=payload.name.strip(),timezone=payload.timezone.strip(),version=1,created_at=now,updated_at=now)
    db.add(value); db.flush()
    db.add(DBHouseholdMember(household_id=value.id,display_name=owner.name or owner.id,linked_user_id=owner.id,role="owner",servings_multiplier=1.0,allergies=list(owner.allergies or []),dietary_restrictions=list(owner.dietary_restrictions or []),disliked_ingredients=list(owner.disliked_ingredients or []),target_calories=owner.target_calories,target_protein_g=owner.target_protein_g,target_carbs_g=owner.target_carbs_g,target_fat_g=owner.target_fat_g,active=True,created_at=now))
    db.commit(); db.refresh(value); return value


def add_household_member(db: Session, household: DBHousehold, payload: HouseholdMemberCreate, owner_user_id: str) -> DBHouseholdMember:
    if payload.linked_user_id not in {None,owner_user_id}: raise HTTPException(status_code=422,detail="Linking another account requires an accepted invitation")
    clean=lambda values: sorted({item.strip().lower() for item in values if item.strip()})
    value=DBHouseholdMember(household_id=household.id,display_name=payload.display_name.strip(),linked_user_id=payload.linked_user_id,role=payload.role.value,servings_multiplier=payload.servings_multiplier,allergies=clean(payload.allergies),dietary_restrictions=clean(payload.dietary_restrictions),disliked_ingredients=clean(payload.disliked_ingredients),target_calories=payload.target_calories,target_protein_g=payload.target_protein_g,target_carbs_g=payload.target_carbs_g,target_fat_g=payload.target_fat_g,active=payload.active,created_at=utcnow())
    household.version+=1; household.updated_at=utcnow(); db.add_all([value,household]); db.commit(); db.refresh(value); return value


def create_leftover(db: Session, household: DBHousehold, payload: LeftoverCreate) -> DBLeftoverBatch:
    prior=_event_by_key(db,household.id,payload.idempotency_key)
    if prior and prior.leftover_id and (existing:=db.get(DBLeftoverBatch,prior.leftover_id)): return existing
    if db.get(DBRecipe,payload.recipe_id) is None: raise HTTPException(status_code=404,detail="Recipe not found")
    if payload.source_plan_id is not None and db.query(DBMealPlan).filter(DBMealPlan.id==payload.source_plan_id,DBMealPlan.household_id==household.id).first() is None: raise HTTPException(status_code=404,detail="Source household meal plan not found")
    policy=None; expires_at=payload.expires_at
    if payload.storage_policy_key:
        policy=db.query(DBStoragePolicy).filter(DBStoragePolicy.policy_key==payload.storage_policy_key,DBStoragePolicy.active.is_(True)).first()
        if policy is None: raise HTTPException(status_code=422,detail="Unknown reviewed storage policy")
        if expires_at is None and policy.duration_max_hours is not None: expires_at=payload.cooked_at+timedelta(hours=float(policy.duration_max_hours))
    now=utcnow(); notes=payload.notes
    if policy is not None:
        suffix=f"Storage policy {policy.policy_key} assumes {policy.storage_state} storage at or below {policy.maximum_temperature_c}°C; inspect food, cold-chain history, packaging, and vulnerable-person considerations."
        notes=f"{notes}\n{suffix}".strip() if notes else suffix
    value=DBLeftoverBatch(household_id=household.id,recipe_id=payload.recipe_id,source_plan_id=payload.source_plan_id,portions_available=payload.portions_available,cooked_at=payload.cooked_at,expires_at=expires_at,frozen=payload.frozen,notes=notes,storage_policy_key=payload.storage_policy_key,version=1,created_at=now,updated_at=now)
    db.add(value); db.flush(); _event(db,household_id=household.id,leftover_id=value.id,event_type=InventoryEventType.LEFTOVER_CREATE,qmin=payload.portions_available,qmax=payload.portions_available,unit="portion",metadata={"storage_policy_key":payload.storage_policy_key},key=payload.idempotency_key); db.commit(); db.refresh(value); return value


def build_batch_prep_tasks(plan: PlanResponse, storage_policies: Iterable[DBStoragePolicy]=()) -> List[BatchPrepTask]:
    grouped: Dict[str,Dict[str,Any]]={}
    for day in plan.days:
        for slot,recipe in day.meals.items():
            entry=grouped.setdefault(recipe.id,{"name":recipe.name,"portions":0.0,"first":day.day,"count":0,"slots":[]}); entry["portions"]+=float(day.portions.get(slot,1.0)); entry["first"]=min(entry["first"],day.day); entry["count"]+=1; entry["slots"].append(f"day_{day.day}:{slot}")
    policy_keys=sorted({value.policy_key for value in storage_policies if value.active and value.food_category=="cooked leftovers"})
    tasks=[BatchPrepTask(recipe_id=identifier,recipe_name=value["name"],total_portions=round(value["portions"],3),first_day=int(value["first"]),scheduled_day=max(1,int(value["first"])-1),occurrences=value["count"],meal_slots=value["slots"],applicable_storage_policies=policy_keys) for identifier,value in grouped.items() if value["count"]>=2]
    return sorted(tasks,key=lambda item:(item.scheduled_day,item.recipe_name.lower(),item.recipe_id))
