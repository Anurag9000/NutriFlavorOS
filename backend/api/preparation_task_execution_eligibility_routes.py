"""Viewer-authorized task-execution eligibility evidence."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.domain.preparation_task_execution_eligibility import (
    PreparationTaskExecutionEligibilityView,
)
from backend.services.household_access_service import require_household_access
from backend.services.preparation_task_execution_eligibility_service import (
    get_task_execution_eligibility,
)
from backend.utils.security import get_current_user


router = APIRouter(
    prefix="/api/v1/households/{household_id}/preparation-operations",
    tags=["household-preparation-task-execution-eligibility"],
)


@router.get(
    "/schedules/{schedule_id}/task-execution-eligibility",
    response_model=PreparationTaskExecutionEligibilityView,
)
def get_task_execution_eligibility_route(
    household_id: str,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    require_household_access(
        db,
        household_id,
        current_user.id,
        HouseholdRole.VIEWER,
    )
    return get_task_execution_eligibility(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
