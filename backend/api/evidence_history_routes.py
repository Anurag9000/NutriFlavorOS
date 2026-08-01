"""Read-only API for immutable conversion and storage-policy evidence.

Evidence mutation remains an offline reviewed operation. Authenticated product
clients may inspect exact versions and apply only an active reviewed conversion.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import DBLeftoverBatch, DBUser, get_db
from backend.domain.evidence_history import (
    ConversionApplicationRequest,
    ConversionApplicationResult,
    IngredientConversionVersionView,
    StoragePolicyVersionView,
)
from backend.domain.household_access import HouseholdRole
from backend.services.evidence_history_service import (
    active_reviewed_storage_policy,
    apply_reviewed_conversion,
    list_conversion_versions,
    list_storage_policy_versions,
    storage_policy_for_leftover,
)
from backend.services.household_access_service import require_household_access
from backend.utils.security import get_current_user


router = APIRouter(
    prefix="/api/v1/food-evidence/history",
    tags=["food-evidence-history"],
)


@router.get(
    "/conversions",
    response_model=list[IngredientConversionVersionView],
)
def conversion_versions_route(
    active_only: bool = Query(default=True),
    reviewed_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _current_user: DBUser = Depends(get_current_user),
):
    return list_conversion_versions(
        db,
        active_only=active_only,
        reviewed_only=reviewed_only,
    )


@router.post(
    "/convert-reviewed",
    response_model=ConversionApplicationResult,
)
def reviewed_conversion_route(
    payload: ConversionApplicationRequest,
    db: Session = Depends(get_db),
    _current_user: DBUser = Depends(get_current_user),
):
    return apply_reviewed_conversion(db, payload)


@router.get(
    "/storage-policies",
    response_model=list[StoragePolicyVersionView],
)
def storage_policy_versions_route(
    active_only: bool = Query(default=True),
    reviewed_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _current_user: DBUser = Depends(get_current_user),
):
    return list_storage_policy_versions(
        db,
        active_only=active_only,
        reviewed_only=reviewed_only,
    )


@router.get(
    "/storage-policies/{policy_key}/active-reviewed",
    response_model=StoragePolicyVersionView,
)
def active_storage_policy_route(
    policy_key: str,
    db: Session = Depends(get_db),
    _current_user: DBUser = Depends(get_current_user),
):
    return active_reviewed_storage_policy(db, policy_key)


@router.get(
    "/households/{household_id}/leftovers/{leftover_id}/storage-policy",
    response_model=StoragePolicyVersionView,
)
def leftover_storage_policy_route(
    household_id: str,
    leftover_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    household, _ = require_household_access(
        db,
        household_id,
        current_user.id,
        HouseholdRole.VIEWER,
    )
    leftover = (
        db.query(DBLeftoverBatch)
        .filter(
            DBLeftoverBatch.id == leftover_id,
            DBLeftoverBatch.household_id == household.id,
        )
        .first()
    )
    if leftover is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    policy = storage_policy_for_leftover(db, leftover.id)
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "leftover_storage_policy_evidence_unavailable",
                "message": "This leftover has no immutable storage-policy version link",
            },
        )
    return policy
