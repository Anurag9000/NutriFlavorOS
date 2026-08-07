"""Household-authorized APIs for preparation repair proposals."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.domain.preparation_execution_aware_repair_proposals import (
    PreparationExecutionAwareRepairPreflightView,
    PreparationExecutionAwareRepairProposalCreateRequest,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
    PreparationRepairProposalAcceptanceView,
    PreparationRepairProposalAcceptedDraftView,
    PreparationRepairProposalCreateRequest,
    PreparationRepairProposalEventView,
    PreparationRepairProposalInvalidateRequest,
    PreparationRepairProposalRejectRequest,
    PreparationRepairProposalStatus,
    PreparationRepairProposalView,
)
from backend.services.household_access_service import require_household_access
from backend.services.preparation_execution_aware_repair_preflight_service import (
    preflight_execution_aware_repair_proposal,
)
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_proposal_invalidation_service import (
    invalidate_repair_proposal,
)
from backend.services.preparation_repair_proposal_read_service import (
    get_repair_proposal,
    get_repair_proposal_acceptance,
    list_repair_proposal_events,
    list_repair_proposals,
    reject_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.utils.security import get_current_user


router = APIRouter(
    prefix="/api/v1/households/{household_id}/preparation-operations/repair-proposals",
    tags=["household-preparation-repair-proposals"],
)


def _access(
    db: Session,
    household_id: str,
    user_id: str,
    role: HouseholdRole,
):
    return require_household_access(
        db,
        household_id,
        user_id,
        role,
    )


@router.post("", response_model=PreparationRepairProposalView)
def create_repair_proposal_route(
    household_id: str,
    payload: PreparationRepairProposalCreateRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return create_repair_proposal(
        db,
        household_id=household_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@router.post(
    "/execution-aware/preflight",
    response_model=PreparationExecutionAwareRepairPreflightView,
)
def preflight_execution_aware_repair_proposal_route(
    household_id: str,
    payload: PreparationExecutionAwareRepairProposalCreateRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Validate exact execution evidence without computing or persisting repair."""

    _access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return preflight_execution_aware_repair_proposal(
        db,
        household_id=household_id,
        payload=payload,
    )


@router.get("", response_model=List[PreparationRepairProposalView])
def list_repair_proposals_route(
    household_id: str,
    status: List[PreparationRepairProposalStatus] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return list_repair_proposals(
        db,
        household_id=household_id,
        statuses=status,
    )


@router.get("/{proposal_id}", response_model=PreparationRepairProposalView)
def get_repair_proposal_route(
    household_id: str,
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return get_repair_proposal(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
    )


@router.get(
    "/{proposal_id}/acceptance",
    response_model=PreparationRepairProposalAcceptanceView,
)
def get_repair_proposal_acceptance_route(
    household_id: str,
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return get_repair_proposal_acceptance(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
    )


@router.get(
    "/{proposal_id}/events",
    response_model=List[PreparationRepairProposalEventView],
)
def list_repair_proposal_events_route(
    household_id: str,
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return list_repair_proposal_events(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
    )


@router.post(
    "/{proposal_id}/accept",
    response_model=PreparationRepairProposalAcceptedDraftView,
)
def accept_repair_proposal_route(
    household_id: str,
    proposal_id: int,
    payload: PreparationRepairProposalAcceptRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return accept_repair_proposal_with_source_guard(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@router.post(
    "/{proposal_id}/reject",
    response_model=PreparationRepairProposalView,
)
def reject_repair_proposal_route(
    household_id: str,
    proposal_id: int,
    payload: PreparationRepairProposalRejectRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return reject_repair_proposal(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@router.post(
    "/{proposal_id}/invalidate",
    response_model=PreparationRepairProposalView,
)
def invalidate_repair_proposal_route(
    household_id: str,
    proposal_id: int,
    payload: PreparationRepairProposalInvalidateRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    _access(db, household_id, current_user.id, HouseholdRole.OWNER)
    return invalidate_repair_proposal(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=current_user.id,
        payload=payload,
    )
