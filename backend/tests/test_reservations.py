from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base, DBHousehold, DBMealPlan, DBPantryItem, DBUser
from backend.domain.household_access import ReservationMutation
from backend.domain.inventory import ReconciledShoppingItem
from backend.services.reservation_service import create_plan_reservations, usable_pantry_intervals, commit_plan_reservations


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine); return sessionmaker(bind=engine)()


def test_reservation_uses_expiry_order_and_subtracts_only_on_commit():
    db=_db(); now=datetime.now(timezone.utc); user=DBUser(id="u@example.com",name="U",hashed_password="x"); db.add(user); db.flush()
    household=DBHousehold(id="h",owner_user_id=user.id,name="H",timezone="UTC",version=1,created_at=now,updated_at=now); db.add(household); db.flush()
    early=DBPantryItem(household_id="h",canonical_name="rice",display_name="Rice",quantity_min=100,quantity_max=100,unit="g",expires_at=now+timedelta(days=1),source="manual",item_metadata={},version=1,created_at=now,updated_at=now)
    late=DBPantryItem(household_id="h",canonical_name="rice",display_name="Rice",quantity_min=100,quantity_max=100,unit="g",expires_at=now+timedelta(days=10),source="manual",item_metadata={},version=1,created_at=now,updated_at=now)
    db.add_all([early,late]); db.flush(); plan=DBMealPlan(user_id=user.id,household_id="h",schema_version="2",plan_data={}); db.add(plan); db.commit()
    need=ReconciledShoppingItem(canonical_name="rice",display_name="Rice",unit="g",required_min=150,required_max=150,pantry_min=200,pantry_max=200,buy_min=0,buy_max=0,coverage_status="covered")
    rows=create_plan_reservations(db,household=household,plan=plan,shopping=[need],reservation_hours=24)
    assert rows[0].pantry_item_id==early.id and sum(r.quantity_max for r in rows)==150
    assert db.get(DBPantryItem,early.id).quantity_max==100
    intervals=usable_pantry_intervals(db,"h")
    assert intervals[("rice","g")]["max"]==50
    commit_plan_reservations(db,"h",plan.id,ReservationMutation(reason="prepared"))
    assert db.get(DBPantryItem,early.id).quantity_max==0
    assert db.get(DBPantryItem,late.id).quantity_max==50
