"""Viewer-authorized task-execution eligibility, snapshot, and lineage evidence."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.domain.preparation_execution_aware_repair import (
    PreparationExecutionAwareRepairSnapshot,
)
from backend.domain.preparation_execution_snapshot import PreparationExecutionSnapshot
from backend.domain.preparation_repair_task_lineage import PreparationRepairTaskLineage
from backend.domain.preparation_task_execution_eligibility import (
    PreparationTaskExecutionEligibilityView,
)
from backend.services.household_access_service import require_household_access
from backend.services.preparation_execution_aware_repair_snapshot_service import (
    build_execution_aware_repair_snapshot,
)
from backend.services.preparation_execution_snapshot_service import (
    get_accepted_preparation_repair_task_lineage,
    get_preparation_execution_snapshot,
)
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


@router.get(
    "/schedules/{schedule_id}/execution-snapshot",
    response_model=PreparationExecutionSnapshot,
)
def get_preparation_execution_snapshot_route(
    household_id: str,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Return the canonical hash-bound execution state used by repair guards."""

    require_household_access(
        db,
        household_id,
        current_user.id,
        HouseholdRole.VIEWER,
    )
    return get_preparation_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )


@router.get(
    "/schedules/{schedule_id}/execution-aware-repair-snapshot",
    response_model=PreparationExecutionAwareRepairSnapshot,
)
def get_execution_aware_repair_snapshot_route(
    household_id: str,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Return the read-only frozen/ready/blocked repair frontier.

    This endpoint performs no repair computation or persistence. A concurrent
    ledger change that makes the richer and canonical projections disagree fails
    closed instead of returning mixed evidence.
    """

    require_household_access(
        db,
        household_id,
        current_user.id,
        HouseholdRole.VIEWER,
    )
    try:
        return build_execution_aware_repair_snapshot(
            db,
            household_id=household_id,
            schedule_id=schedule_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "execution_aware_repair_snapshot_inconsistent",
                "message": "Execution evidence changed while the repair frontier was read",
            },
        ) from exc


@router.get(
    "/repair-proposals/{proposal_id}/task-lineage",
    response_model=PreparationRepairTaskLineage,
)
def get_accepted_preparation_repair_task_lineage_route(
    household_id: str,
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Return immutable source→replacement task lineage after acceptance."""

    require_household_access(
        db,
        household_id,
        current_user.id,
        HouseholdRole.VIEWER,
    )
    return get_accepted_preparation_repair_task_lineage(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
    )
