from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.database import CURRENT_PLAN_SCHEMA_VERSION, DBHouseholdMember, DBInventoryEvent, DBMealPlan, DBUser, get_db
from backend.domain.inventory import BatchPrepTask, HouseholdCreate, HouseholdMemberCreate, HouseholdMemberView, HouseholdView, InventoryEventType, InventoryEventView, InventoryMutation, LeftoverConsume, LeftoverCreate, LeftoverView, PantryItemCreate, PantryItemView, ReconciledShoppingItem
from backend.models import PlanResponse
from backend.services.inventory_service import add_household_member, add_pantry_item, build_batch_prep_tasks, consume_leftover, consume_pantry_item, create_household, create_leftover, list_households, list_leftovers, list_pantry_items, reconcile_shopping_list, require_household_owner, set_pantry_quantity
from backend.utils.security import get_current_user
router=APIRouter(prefix="/api/v1/households",tags=["households"])
def _latest_plan(db:Session,user_id:str)->DBMealPlan:
    value=db.query(DBMealPlan).filter(DBMealPlan.user_id==user_id).order_by(DBMealPlan.created_at.desc(),DBMealPlan.id.desc()).first()
    if value is None: raise HTTPException(status_code=404,detail="No meal plan found")
    if value.schema_version!=CURRENT_PLAN_SCHEMA_VERSION: raise HTTPException(status_code=409,detail={"code":"stored_plan_schema_mismatch","message":"Regenerate the meal plan before using household features","stored_version":value.schema_version,"required_version":CURRENT_PLAN_SCHEMA_VERSION})
    return value
@router.post("",response_model=HouseholdView,status_code=status.HTTP_201_CREATED)
def create_household_route(payload:HouseholdCreate,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)): return create_household(db,current_user,payload)
@router.get("",response_model=list[HouseholdView])
def list_households_route(db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)): return list_households(db,current_user.id)
@router.get("/{household_id}")
def get_household_route(household_id:str,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    household=require_household_owner(db,household_id,current_user.id); members=db.query(DBHouseholdMember).filter(DBHouseholdMember.household_id==household.id).order_by(DBHouseholdMember.id).all()
    return {"household":HouseholdView.model_validate(household),"members":[HouseholdMemberView.model_validate(x) for x in members],"active_servings_multiplier":round(sum(x.servings_multiplier for x in members if x.active),3),"planning_status":"household_restrictions_available; member-specific nutrition optimization pending"}
@router.post("/{household_id}/members",response_model=HouseholdMemberView,status_code=201)
def add_member_route(household_id:str,payload:HouseholdMemberCreate,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    return add_household_member(db,require_household_owner(db,household_id,current_user.id),payload,current_user.id)
@router.get("/{household_id}/pantry",response_model=list[PantryItemView])
def pantry_route(household_id:str,include_empty:bool=Query(False),db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    household=require_household_owner(db,household_id,current_user.id); return [PantryItemView.model_validate(x) for x in list_pantry_items(db,household.id,include_empty=include_empty)]
@router.post("/{household_id}/pantry",response_model=PantryItemView,status_code=201)
def add_pantry_route(household_id:str,payload:PantryItemCreate,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    return PantryItemView.model_validate(add_pantry_item(db,require_household_owner(db,household_id,current_user.id),payload))
@router.post("/{household_id}/pantry/{item_id}/consume",response_model=PantryItemView)
def consume_pantry_route(household_id:str,item_id:int,payload:InventoryMutation,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    return PantryItemView.model_validate(consume_pantry_item(db,require_household_owner(db,household_id,current_user.id),item_id,payload))
@router.post("/{household_id}/pantry/{item_id}/discard",response_model=PantryItemView)
def discard_pantry_route(household_id:str,item_id:int,payload:InventoryMutation,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    return PantryItemView.model_validate(consume_pantry_item(db,require_household_owner(db,household_id,current_user.id),item_id,payload,event_type=InventoryEventType.DISCARD))
@router.put("/{household_id}/pantry/{item_id}",response_model=PantryItemView)
def adjust_pantry_route(household_id:str,item_id:int,payload:InventoryMutation,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    return PantryItemView.model_validate(set_pantry_quantity(db,require_household_owner(db,household_id,current_user.id),item_id,payload))
@router.get("/{household_id}/inventory-events",response_model=list[InventoryEventView])
def inventory_events_route(household_id:str,limit:int=Query(100,ge=1,le=1000),db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    household=require_household_owner(db,household_id,current_user.id); rows=db.query(DBInventoryEvent).filter(DBInventoryEvent.household_id==household.id).order_by(DBInventoryEvent.created_at.desc(),DBInventoryEvent.id.desc()).limit(limit).all(); return [InventoryEventView.model_validate(x) for x in rows]
@router.post("/{household_id}/leftovers",response_model=LeftoverView,status_code=201)
def create_leftover_route(household_id:str,payload:LeftoverCreate,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    return LeftoverView.model_validate(create_leftover(db,require_household_owner(db,household_id,current_user.id),payload))
@router.get("/{household_id}/leftovers",response_model=list[LeftoverView])
def leftovers_route(household_id:str,include_empty:bool=Query(False),db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    household=require_household_owner(db,household_id,current_user.id); return [LeftoverView.model_validate(x) for x in list_leftovers(db,household.id,include_empty=include_empty)]
@router.post("/{household_id}/leftovers/{leftover_id}/consume",response_model=LeftoverView)
def consume_leftover_route(household_id:str,leftover_id:int,payload:LeftoverConsume,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    return LeftoverView.model_validate(consume_leftover(db,require_household_owner(db,household_id,current_user.id),leftover_id,payload))
@router.get("/{household_id}/shopping-reconciliation",response_model=list[ReconciledShoppingItem])
def shopping_reconciliation_route(household_id:str,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    household=require_household_owner(db,household_id,current_user.id); stored=_latest_plan(db,current_user.id)
    try: plan=PlanResponse.model_validate(stored.plan_data)
    except ValueError as exc: raise HTTPException(status_code=409,detail="Stored plan is incompatible; regenerate it") from exc
    return reconcile_shopping_list(plan,list_pantry_items(db,household.id))
@router.get("/{household_id}/batch-prep",response_model=list[BatchPrepTask])
def batch_prep_route(household_id:str,db:Session=Depends(get_db),current_user:DBUser=Depends(get_current_user)):
    require_household_owner(db,household_id,current_user.id); return build_batch_prep_tasks(PlanResponse.model_validate(_latest_plan(db,current_user.id).plan_data))
