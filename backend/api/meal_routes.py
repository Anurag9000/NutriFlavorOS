from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import DBMealPlan, DBUser, get_db
from backend.engines.plan_generator import InfeasiblePlanError, PlanGenerator
from backend.models import DailyPlan, PlanResponse, Recipe, UserProfile
from backend.utils.security import get_current_user, require_self
from backend.utils.user_profiles import apply_profile, db_user_to_profile


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/meals", tags=["meals"])
_generator: Optional[PlanGenerator] = None


class RegenerateDayPayload(BaseModel):
    user_id: str
    day_index: int = Field(ge=0, le=30)


class SwapMealPayload(BaseModel):
    user_id: str
    meal_slot: str = Field(min_length=1, max_length=80)


def get_generator() -> PlanGenerator:
    global _generator
    if _generator is None:
        _generator = PlanGenerator()
    return _generator


def _latest_plan(db: Session, user_id: str) -> Optional[DBMealPlan]:
    return (
        db.query(DBMealPlan)
        .filter(DBMealPlan.user_id == user_id)
        .order_by(DBMealPlan.created_at.desc(), DBMealPlan.id.desc())
        .first()
    )


def _raise_planner_error(exc: Exception) -> None:
    if isinstance(exc, (InfeasiblePlanError, ValueError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    logger.exception("Unexpected meal planner failure", exc_info=exc)
    raise HTTPException(status_code=500, detail="Meal plan generation failed") from exc


@router.get("/plan/{user_id}", response_model=PlanResponse)
def get_meal_plan(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> PlanResponse:
    require_self(user_id, current_user)
    stored = _latest_plan(db, user_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="No meal plan found")
    try:
        return PlanResponse.model_validate(stored.plan_data)
    except ValueError as exc:
        logger.exception("Stored plan failed schema validation", exc_info=exc)
        raise HTTPException(status_code=500, detail="Stored meal plan is invalid") from exc


@router.post("/generate", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def generate_meal_plan(
    profile: Optional[UserProfile] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> PlanResponse:
    if profile is not None:
        apply_profile(current_user, profile)
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    persisted_profile = db_user_to_profile(current_user)
    try:
        plan = get_generator().create_plan(
            persisted_profile,
            days=7,
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_planner_error(exc)
        raise AssertionError("unreachable")

    db.add(DBMealPlan(user_id=current_user.id, plan_data=plan.model_dump(mode="json")))
    db.commit()
    return plan


@router.post("/regenerate_day", response_model=DailyPlan)
def regenerate_day(
    payload: RegenerateDayPayload,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> DailyPlan:
    require_self(payload.user_id, current_user)
    profile = db_user_to_profile(current_user)

    try:
        generated = get_generator().create_plan(profile, days=1, user_id=current_user.id)
    except Exception as exc:
        _raise_planner_error(exc)
        raise AssertionError("unreachable")

    new_day = generated.days[0].model_copy(update={"day": payload.day_index + 1})
    stored = _latest_plan(db, current_user.id)
    if stored is None:
        replacement = generated.model_copy(update={"days": [new_day]})
        db.add(DBMealPlan(user_id=current_user.id, plan_data=replacement.model_dump(mode="json")))
    else:
        current_plan = PlanResponse.model_validate(stored.plan_data)
        if payload.day_index >= len(current_plan.days):
            raise HTTPException(status_code=404, detail="Plan day not found")
        updated_days = list(current_plan.days)
        updated_days[payload.day_index] = new_day
        stored.plan_data = current_plan.model_copy(update={"days": updated_days}).model_dump(mode="json")
        db.add(stored)

    db.commit()
    return new_day


@router.post("/swap_meal", response_model=Recipe)
def swap_meal(
    payload: SwapMealPayload,
    current_user: DBUser = Depends(get_current_user),
) -> Recipe:
    require_self(payload.user_id, current_user)
    profile = db_user_to_profile(current_user)

    try:
        generated = get_generator().create_plan(profile, days=1, user_id=current_user.id)
    except Exception as exc:
        _raise_planner_error(exc)
        raise AssertionError("unreachable")

    normalized_slot = payload.meal_slot.strip().lower()
    for slot, recipe in generated.days[0].meals.items():
        if slot.lower() == normalized_slot:
            return recipe
    raise HTTPException(status_code=404, detail="Meal slot not found")
