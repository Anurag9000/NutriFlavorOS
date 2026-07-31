from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBInventoryEvent, DBRecipe, DBUser
from backend.domain.inventory import HouseholdCreate, InventoryMutation, LeftoverConsume, LeftoverCreate, PantryItemCreate, QuantityRange
from backend.models import DailyPlan, PlanResponse, Recipe
from backend.services.inventory_service import add_pantry_item, build_batch_prep_tasks, consume_leftover, consume_pantry_item, create_household, create_leftover, list_pantry_items, reconcile_shopping_list

@pytest.fixture()
def db():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool); Session=sessionmaker(bind=engine,autoflush=False,autocommit=False); Base.metadata.create_all(engine); session=Session()
    session.add(DBUser(id="owner@example.com",hashed_password="x",name="Owner",allergies=[],dietary_restrictions=[],disliked_ingredients=[],liked_ingredients=[],health_conditions=[],medications=[]))
    session.add(DBRecipe(id="rice-bowl",name="Rice Bowl",description="",ingredients=["200 g rice"],ingredient_data=[],servings=1,calories=300,macros={"protein":8,"carbs":60,"fat":3},flavor_profile={},tags=[],instructions=[],estimated_cost=2,nutrition_basis="per_serving")); session.commit()
    try: yield session
    finally: session.close()

def test_inventory_is_canonical_idempotent_and_versioned(db):
    owner=db.get(DBUser,"owner@example.com"); household=create_household(db,owner,HouseholdCreate(name="Home",timezone="Asia/Kolkata")); payload=PantryItemCreate(ingredient_name="Rice",quantity=QuantityRange(quantity_min=1,quantity_max=1,unit="kg"),idempotency_key="purchase-rice-0001")
    first=add_pantry_item(db,household,payload); second=add_pantry_item(db,household,payload); assert first.id==second.id; assert first.unit=="g"; assert first.quantity_min==first.quantity_max==1000; assert db.query(DBInventoryEvent).count()==1
    consumed=consume_pantry_item(db,household,first.id,InventoryMutation(quantity=QuantityRange(quantity_min=200,quantity_max=200,unit="g"),expected_version=1,idempotency_key="consume-rice-0001")); assert consumed.quantity_min==consumed.quantity_max==800; assert consumed.version==2
    with pytest.raises(HTTPException) as exc: consume_pantry_item(db,household,first.id,InventoryMutation(quantity=QuantityRange(quantity_min=1,quantity_max=1,unit="g"),expected_version=1))
    assert exc.value.status_code==409

def test_shopping_reconciliation_uses_ranges_and_ignores_expired(db):
    owner=db.get(DBUser,"owner@example.com"); household=create_household(db,owner,HouseholdCreate(name="Home")); add_pantry_item(db,household,PantryItemCreate(ingredient_name="rice",quantity=QuantityRange(quantity_min=.7,quantity_max=.8,unit="kg"),expires_at=datetime.now(timezone.utc)+timedelta(days=2))); add_pantry_item(db,household,PantryItemCreate(ingredient_name="rice",quantity=QuantityRange(quantity_min=500,quantity_max=500,unit="g"),expires_at=datetime.now(timezone.utc)-timedelta(days=1)))
    recipe=Recipe(id="rice-bowl",name="Rice Bowl",description="",ingredients=["200 g rice"],calories=300,macros={"protein":8,"carbs":60,"fat":3}); plan=PlanResponse(user_id=owner.id,days=[DailyPlan(day=1,meals={"Dinner":recipe},portions={"Dinner":1},total_stats={},scores={})],shopping_list={"Grains":{"rice":{"display_name":"Rice","quantities":[{"quantity_min":1000,"quantity_max":1200,"unit":"g"}],"source_recipe_ids":["rice-bowl"]}}})
    item=reconcile_shopping_list(plan,list_pantry_items(db,household.id))[0]; assert item.pantry_min==700; assert item.pantry_max==800; assert item.buy_min==200; assert item.buy_max==500; assert item.coverage_status=="partial"; assert item.expiring_quantity_max==800

def test_leftover_ledger_and_batch_prep(db):
    owner=db.get(DBUser,"owner@example.com"); household=create_household(db,owner,HouseholdCreate(name="Home")); leftover=create_leftover(db,household,LeftoverCreate(recipe_id="rice-bowl",portions_available=3,cooked_at=datetime.now(timezone.utc),idempotency_key="leftover-create-0001")); remaining=consume_leftover(db,household,leftover.id,LeftoverConsume(portions=1.25,expected_version=1,idempotency_key="leftover-eat-0001")); assert remaining.portions_available==pytest.approx(1.75)
    recipe=Recipe(id="rice-bowl",name="Rice Bowl",description="",ingredients=["200 g rice"],calories=300,macros={"protein":8,"carbs":60,"fat":3}); plan=PlanResponse(user_id=owner.id,days=[DailyPlan(day=1,meals={"Dinner":recipe},portions={"Dinner":1.5},total_stats={},scores={}),DailyPlan(day=3,meals={"Lunch":recipe},portions={"Lunch":1.0},total_stats={},scores={})]); task=build_batch_prep_tasks(plan)[0]; assert task.total_portions==2.5; assert task.occurrences==2; assert task.storage_guidance_status=="requires_verified_recipe_specific_policy"
