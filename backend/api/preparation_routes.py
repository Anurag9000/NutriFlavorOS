"""Authenticated preparation-resource scheduling API."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.database import DBUser
from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.utils.security import get_current_user


router = APIRouter(prefix="/api/v1/preparation", tags=["preparation"])


@router.post("/schedule", response_model=PreparationScheduleResponse)
def schedule_preparation(
    payload: PreparationScheduleRequest,
    _: DBUser = Depends(get_current_user),
) -> PreparationScheduleResponse:
    """Schedule only explicitly declared preparation work and capacities."""

    return build_preparation_schedule(payload)
