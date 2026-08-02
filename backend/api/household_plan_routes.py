"""Role-aware APIs for persisted household meal-plan review and approval."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.domain.household_plan_lifecycle import (
    HouseholdPlanEventType,
    HouseholdPlanEventView,
    HouseholdPlanStatus,
    HouseholdPlanTransitionRequest,
    PersistedHouseholdPlanView,
)
from backend.services.household_access_service import require_household_access
from backend.services.household_plan_lifecycle_service import (
    get_household_plan,
    list_household_plan_events,
    list_household_plans,
    transition_household_plan,
)
from backend.utils.security import get_current_user


router = APIRouter(
    prefix="/api/v1/households/{household_id}/plans",
    tags=["household-plan-lifecycle"],
)


def _authorize(
    db: Session,
    household_id: str,
    user_id: str,
    role: HouseholdRole,
) -> None:
    require_household_access(db, household_id, user_id, role)


@router.get("", response_model=List[PersistedHouseholdPlanView])
def list_household_plans_route(
    household_id: str,
    status: List[HouseholdPlanStatus] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _authorize(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return list_household_plans(
        db,
        household_id=household_id,
        statuses=status,
    )


@router.get("/{plan_id}", response_model=PersistedHouseholdPlanView)
def get_household_plan_route(
    household_id: str,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _authorize(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return get_household_plan(
        db,
        household_id=household_id,
        plan_id=plan_id,
    )


@router.post("/{plan_id}/approve", response_model=PersistedHouseholdPlanView)
def approve_household_plan_route(
    household_id: str,
    plan_id: int,
    payload: HouseholdPlanTransitionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _authorize(db, household_id, current_user.id, HouseholdRole.OWNER)
    return transition_household_plan(
        db,
        household_id=household_id,
        plan_id=plan_id,
        actor_user_id=current_user.id,
        event_type=HouseholdPlanEventType.APPROVED,
        payload=payload,
    )


@router.post("/{plan_id}/cancel", response_model=PersistedHouseholdPlanView)
def cancel_household_plan_route(
    household_id: str,
    plan_id: int,
    payload: HouseholdPlanTransitionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _authorize(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return transition_household_plan(
        db,
        household_id=household_id,
        plan_id=plan_id,
        actor_user_id=current_user.id,
        event_type=HouseholdPlanEventType.CANCELLED,
        payload=payload,
    )


@router.get(
    "/{plan_id}/events",
    response_model=List[HouseholdPlanEventView],
)
def list_household_plan_events_route(
    household_id: str,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _authorize(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return list_household_plan_events(
        db,
        household_id=household_id,
        plan_id=plan_id,
    )
