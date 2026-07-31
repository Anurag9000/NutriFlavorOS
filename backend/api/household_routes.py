"""Role-aware household, inventory, invitation, planning, and reservation API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import (
    CURRENT_PLAN_SCHEMA_VERSION,
    DBHouseholdMember,
    DBInventoryEvent,
    DBMealPlan,
    DBStoragePolicy,
    DBUser,
    get_db,
)
from backend.domain.household_access import (
    HouseholdMemberUpdate,
    HouseholdPlanRequest,
    HouseholdPlanResponse,
    HouseholdRole,
    InvitationAccept,
    InvitationCreate,
    InvitationView,
    ReservationMutation,
    ReservationView,
)
from backend.domain.inventory import (
    BatchPrepTask,
    HouseholdCreate,
    HouseholdMemberCreate,
    HouseholdMemberView,
    HouseholdView,
    InventoryEventType,
    InventoryEventView,
    InventoryMutation,
    LeftoverConsume,
    LeftoverCreate,
    LeftoverView,
    PantryItemCreate,
    PantryItemView,
    ReconciledShoppingItem,
)
from backend.engines.household_plan_generator import (
    HouseholdPlanningError,
    create_household_plan,
)
from backend.engines.plan_generator import InfeasiblePlanError
from backend.models import PlanResponse
from backend.services.household_access_service import (
    accept_invitation,
    create_invitation,
    list_accessible_households,
    list_invitations,
    require_household_access,
    revoke_invitation,
    update_member,
)
from backend.services.inventory_service_v4 import (
    add_household_member,
    add_pantry_item,
    build_batch_prep_tasks,
    consume_leftover,
    consume_pantry_item,
    create_household,
    create_leftover,
    list_leftovers,
    list_pantry_items,
    reconcile_shopping_list,
    set_pantry_quantity,
)
from backend.services.reservation_service import (
    commit_plan_reservations,
    list_reservations,
    release_plan_reservations,
)
from backend.utils.security import get_current_user


router = APIRouter(prefix="/api/v1/households", tags=["households"])


def _latest_household_plan(db: Session, household_id: str) -> DBMealPlan:
    value = (
        db.query(DBMealPlan)
        .filter(DBMealPlan.household_id == household_id)
        .order_by(DBMealPlan.created_at.desc(), DBMealPlan.id.desc())
        .first()
    )
    if value is None:
        raise HTTPException(status_code=404, detail="No household meal plan found")
    if value.schema_version != CURRENT_PLAN_SCHEMA_VERSION:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stored_plan_schema_mismatch",
                "message": "Regenerate the household meal plan",
                "stored_version": value.schema_version,
                "required_version": CURRENT_PLAN_SCHEMA_VERSION,
            },
        )
    return value


def _plan_response(stored: DBMealPlan) -> PlanResponse:
    try:
        return PlanResponse.model_validate(stored.plan_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stored_plan_incompatible",
                "message": "Stored plan is incompatible; regenerate it",
            },
        ) from exc


@router.post("", response_model=HouseholdView, status_code=status.HTTP_201_CREATED)
def create_household_route(
    payload: HouseholdCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    value = create_household(db, current_user, payload)
    return HouseholdView.model_validate(value).model_copy(
        update={"current_role": HouseholdRole.OWNER}
    )


@router.get("", response_model=list[HouseholdView])
def list_households_route(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    return [
        HouseholdView.model_validate(household).model_copy(
            update={"current_role": role}
        )
        for household, role in list_accessible_households(db, current_user.id)
    ]


@router.post("/invitations/accept", response_model=HouseholdMemberView)
def accept_invitation_route(
    payload: InvitationAccept,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    return HouseholdMemberView.model_validate(
        accept_invitation(db, payload.token, current_user)
    )


@router.get("/{household_id}")
def get_household_route(
    household_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    household, role = require_household_access(
        db, household_id, current_user.id, HouseholdRole.VIEWER
    )
    members = (
        db.query(DBHouseholdMember)
        .filter(DBHouseholdMember.household_id == household.id)
        .order_by(DBHouseholdMember.id)
        .all()
    )
    active = [member for member in members if member.active]
    return {
        "household": HouseholdView.model_validate(household).model_copy(
            update={"current_role": role}
        ),
        "role": role,
        "members": [HouseholdMemberView.model_validate(value) for value in members],
        "active_servings_multiplier": round(
            sum(member.servings_multiplier for member in active), 3
        ),
        "planning_status": (
            "member_targets_and_hard_restrictions_supported; "
            "pantry-aware planning and reservations available"
        ),
    }


@router.post("/{household_id}/members", response_model=HouseholdMemberView, status_code=status.HTTP_201_CREATED)
def add_member_route(household_id: str, payload: HouseholdMemberCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.OWNER)
    return HouseholdMemberView.model_validate(add_household_member(db, household, payload, current_user.id))


@router.patch("/{household_id}/members/{member_id}", response_model=HouseholdMemberView)
def update_member_route(household_id: str, member_id: int, payload: HouseholdMemberUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.OWNER)
    return HouseholdMemberView.model_validate(update_member(db, household, member_id, payload))


@router.post("/{household_id}/invitations", response_model=InvitationView, status_code=status.HTTP_201_CREATED)
def create_invitation_route(household_id: str, payload: InvitationCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.OWNER)
    return create_invitation(db, household, current_user, payload)


@router.get("/{household_id}/invitations", response_model=list[InvitationView])
def list_invitations_route(household_id: str, include_closed: bool = Query(False), db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    require_household_access(db, household_id, current_user.id, HouseholdRole.OWNER)
    return [InvitationView.model_validate(value) for value in list_invitations(db, household_id, include_closed)]


@router.delete("/{household_id}/invitations/{invitation_id}", response_model=InvitationView)
def revoke_invitation_route(household_id: str, invitation_id: str, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    require_household_access(db, household_id, current_user.id, HouseholdRole.OWNER)
    return InvitationView.model_validate(revoke_invitation(db, household_id, invitation_id))


@router.get("/{household_id}/pantry", response_model=list[PantryItemView])
def pantry_route(household_id: str, include_empty: bool = Query(False), db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return [PantryItemView.model_validate(value) for value in list_pantry_items(db, household.id, include_empty=include_empty)]


@router.post("/{household_id}/pantry", response_model=PantryItemView, status_code=status.HTTP_201_CREATED)
def add_pantry_route(household_id: str, payload: PantryItemCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return PantryItemView.model_validate(add_pantry_item(db, household, payload))


@router.post("/{household_id}/pantry/{item_id}/consume", response_model=PantryItemView)
def consume_pantry_route(household_id: str, item_id: int, payload: InventoryMutation, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return PantryItemView.model_validate(consume_pantry_item(db, household, item_id, payload))


@router.post("/{household_id}/pantry/{item_id}/discard", response_model=PantryItemView)
def discard_pantry_route(household_id: str, item_id: int, payload: InventoryMutation, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return PantryItemView.model_validate(consume_pantry_item(db, household, item_id, payload, event_type=InventoryEventType.DISCARD))


@router.put("/{household_id}/pantry/{item_id}", response_model=PantryItemView)
def adjust_pantry_route(household_id: str, item_id: int, payload: InventoryMutation, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return PantryItemView.model_validate(set_pantry_quantity(db, household, item_id, payload))


@router.get("/{household_id}/inventory-events", response_model=list[InventoryEventView])
def inventory_events_route(household_id: str, limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    rows = db.query(DBInventoryEvent).filter(DBInventoryEvent.household_id == household.id).order_by(DBInventoryEvent.created_at.desc(), DBInventoryEvent.id.desc()).limit(limit).all()
    return [InventoryEventView.model_validate(value) for value in rows]


@router.post("/{household_id}/leftovers", response_model=LeftoverView, status_code=status.HTTP_201_CREATED)
def create_leftover_route(household_id: str, payload: LeftoverCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return LeftoverView.model_validate(create_leftover(db, household, payload))


@router.get("/{household_id}/leftovers", response_model=list[LeftoverView])
def leftovers_route(household_id: str, include_empty: bool = Query(False), db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return [LeftoverView.model_validate(value) for value in list_leftovers(db, household.id, include_empty=include_empty)]


@router.post("/{household_id}/leftovers/{leftover_id}/consume", response_model=LeftoverView)
def consume_leftover_route(household_id: str, leftover_id: int, payload: LeftoverConsume, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return LeftoverView.model_validate(consume_leftover(db, household, leftover_id, payload))


@router.post("/{household_id}/plans", response_model=HouseholdPlanResponse, status_code=status.HTTP_201_CREATED)
def generate_household_plan_route(household_id: str, payload: HouseholdPlanRequest, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    owner = db.get(DBUser, household.owner_user_id)
    if owner is None:
        raise HTTPException(status_code=409, detail="Household owner profile is unavailable")
    try:
        return create_household_plan(db=db, household=household, owner=owner, request=payload)
    except (HouseholdPlanningError, InfeasiblePlanError, ValueError) as exc:
        raise HTTPException(status_code=422, detail={"code": "household_plan_infeasible", "message": str(exc), "diagnostics": getattr(exc, "diagnostics", {})}) from exc


@router.get("/{household_id}/shopping-reconciliation", response_model=list[ReconciledShoppingItem])
def shopping_reconciliation_route(household_id: str, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return reconcile_shopping_list(_plan_response(_latest_household_plan(db, household.id)), list_pantry_items(db, household.id))


@router.get("/{household_id}/batch-prep", response_model=list[BatchPrepTask])
def batch_prep_route(household_id: str, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    policies = db.query(DBStoragePolicy).filter(DBStoragePolicy.active.is_(True)).all()
    return build_batch_prep_tasks(_plan_response(_latest_household_plan(db, household.id)), policies)


@router.get("/{household_id}/reservations", response_model=list[ReservationView])
def reservations_route(household_id: str, include_closed: bool = Query(False), db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.VIEWER)
    return [ReservationView.model_validate(value) for value in list_reservations(db, household.id, include_closed=include_closed)]


@router.post("/{household_id}/plans/{plan_id}/reservations/release", response_model=list[ReservationView])
def release_reservations_route(household_id: str, plan_id: int, payload: ReservationMutation, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return [ReservationView.model_validate(value) for value in release_plan_reservations(db, household.id, plan_id, payload)]


@router.post("/{household_id}/plans/{plan_id}/reservations/commit", response_model=list[ReservationView])
def commit_reservations_route(household_id: str, plan_id: int, payload: ReservationMutation, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    household, _ = require_household_access(db, household_id, current_user.id, HouseholdRole.EDITOR)
    return [ReservationView.model_validate(value) for value in commit_plan_reservations(db, household.id, plan_id, payload)]
