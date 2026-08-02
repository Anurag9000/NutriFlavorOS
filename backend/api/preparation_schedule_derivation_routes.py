"""Authorized read-only API for preparation schedule derivation evidence."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.domain.preparation_schedule_derivation import (
    PreparationScheduleDerivationEvidenceView,
)
from backend.services.household_access_service import require_household_access
from backend.services.preparation_schedule_derivation_service import (
    get_schedule_derivation_evidence,
)
from backend.utils.security import get_current_user


router = APIRouter(
    prefix="/api/v1/households/{household_id}/preparation-operations",
    tags=["household-preparation-schedule-derivation"],
)


@router.get(
    "/schedules/{schedule_id}/derivation",
    response_model=PreparationScheduleDerivationEvidenceView,
)
def get_schedule_derivation_evidence_route(
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
    return get_schedule_derivation_evidence(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
