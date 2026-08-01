"""Authorized household APIs for preparation calendars and schedules."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.domain.preparation_operations import (
    PersistedPreparationScheduleView,
    PreparationScheduleEventType,
    PreparationScheduleEventView,
    PreparationScheduleStatus,
    ResourceCalendarVersionCreate,
    ResourceCalendarVersionView,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.services.household_access_service import require_household_access
from backend.services.preparation_operations_integrity_service import (
    create_persisted_schedule,
    get_persisted_schedule,
    list_persisted_schedules,
    transition_schedule,
)
from backend.services.preparation_operations_service import (
    get_resource_calendar,
    list_resource_calendars,
    list_schedule_events,
    register_resource_calendar,
)
from backend.utils.security import get_current_user


router = APIRouter(
    prefix="/api/v1/households/{household_id}/preparation-operations",
    tags=["household-preparation-operations"],
)


def _access(
    db: Session,
    household_id: str,
    user_id: str,
    role: HouseholdRole,
):
    household, membership = require_household_access(
        db,
        household_id,
        user_id,
        role,
    )
    return household, membership


@router.post(
    "/resource-calendars",
    response_model=ResourceCalendarVersionView,
)
def create_resource_calendar_route(
    household_id: str,
    payload: ResourceCalendarVersionCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.OWNER)
    return register_resource_calendar(
        db,
        household_id=household_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "/resource-calendars",
    response_model=List[ResourceCalendarVersionView],
)
def list_resource_calendars_route(
    household_id: str,
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return list_resource_calendars(
        db,
        household_id=household_id,
        active_only=active_only,
    )


@router.get(
    "/resource-calendars/{calendar_id}",
    response_model=ResourceCalendarVersionView,
)
def get_resource_calendar_route(
    household_id: str,
    calendar_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return get_resource_calendar(
        db,
        household_id=household_id,
        calendar_id=calendar_id,
    )


@router.post(
    "/schedules",
    response_model=PersistedPreparationScheduleView,
)
def create_persisted_schedule_route(
    household_id: str,
    payload: PersistedScheduleCreateRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return create_persisted_schedule(
        db,
        household_id=household_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "/schedules",
    response_model=List[PersistedPreparationScheduleView],
)
def list_persisted_schedules_route(
    household_id: str,
    status: List[PreparationScheduleStatus] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return list_persisted_schedules(
        db,
        household_id=household_id,
        statuses=status,
    )


@router.get(
    "/schedules/{schedule_id}",
    response_model=PersistedPreparationScheduleView,
)
def get_persisted_schedule_route(
    household_id: str,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return get_persisted_schedule(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )


def _transition(
    *,
    db: Session,
    household_id: str,
    schedule_id: int,
    current_user: DBUser,
    payload: ScheduleStateTransitionRequest,
    event_type: PreparationScheduleEventType,
    required_role: HouseholdRole,
):
    _access(db, household_id, current_user.id, required_role)
    return transition_schedule(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        actor_user_id=current_user.id,
        event_type=event_type,
        payload=payload,
    )


@router.post(
    "/schedules/{schedule_id}/approve",
    response_model=PersistedPreparationScheduleView,
)
def approve_schedule_route(
    household_id: str,
    schedule_id: int,
    payload: ScheduleStateTransitionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    return _transition(
        db=db,
        household_id=household_id,
        schedule_id=schedule_id,
        current_user=current_user,
        payload=payload,
        event_type=PreparationScheduleEventType.APPROVED,
        required_role=HouseholdRole.OWNER,
    )


@router.post(
    "/schedules/{schedule_id}/complete",
    response_model=PersistedPreparationScheduleView,
)
def complete_schedule_route(
    household_id: str,
    schedule_id: int,
    payload: ScheduleStateTransitionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    return _transition(
        db=db,
        household_id=household_id,
        schedule_id=schedule_id,
        current_user=current_user,
        payload=payload,
        event_type=PreparationScheduleEventType.COMPLETED,
        required_role=HouseholdRole.EDITOR,
    )


@router.post(
    "/schedules/{schedule_id}/cancel",
    response_model=PersistedPreparationScheduleView,
)
def cancel_schedule_route(
    household_id: str,
    schedule_id: int,
    payload: ScheduleStateTransitionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    return _transition(
        db=db,
        household_id=household_id,
        schedule_id=schedule_id,
        current_user=current_user,
        payload=payload,
        event_type=PreparationScheduleEventType.CANCELLED,
        required_role=HouseholdRole.EDITOR,
    )


@router.post(
    "/schedules/{schedule_id}/invalidate",
    response_model=PersistedPreparationScheduleView,
)
def invalidate_schedule_route(
    household_id: str,
    schedule_id: int,
    payload: ScheduleStateTransitionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    return _transition(
        db=db,
        household_id=household_id,
        schedule_id=schedule_id,
        current_user=current_user,
        payload=payload,
        event_type=PreparationScheduleEventType.INVALIDATED,
        required_role=HouseholdRole.OWNER,
    )


@router.get(
    "/schedules/{schedule_id}/events",
    response_model=List[PreparationScheduleEventView],
)
def list_schedule_events_route(
    household_id: str,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return list_schedule_events(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
