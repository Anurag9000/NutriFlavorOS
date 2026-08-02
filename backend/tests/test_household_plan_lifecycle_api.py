from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import household_plan_routes
from backend.database import Base, DBHousehold, DBMealPlan, DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.meal_plan_lifecycle_models import DBHouseholdPlanEvent
from backend.utils.security import get_current_user


HOUSEHOLD_ID = "plan-api-home"
OWNER_ID = "plan-api-owner@example.test"
VIEWER_ID = "plan-api-viewer@example.test"
OUTSIDER_ID = "plan-api-outsider@example.test"
ROLE_RANK = {
    HouseholdRole.VIEWER: 1,
    HouseholdRole.EDITOR: 2,
    HouseholdRole.OWNER: 3,
}


def _plan_payload() -> dict:
    recipe = {
        "id": "api-recipe",
        "name": "API reviewed meal",
        "description": "Fixture recipe",
        "ingredients": [],
        "ingredient_lines": [],
        "servings": 2,
        "calories": 400,
        "macros": {},
        "flavor_profile": {},
        "tags": [],
        "instructions": ["Cook"],
        "estimated_cost": 100,
        "nutrition_basis": "per_serving",
    }
    return {
        "user_id": OWNER_ID,
        "days": [
            {
                "day": 1,
                "meals": {"dinner": recipe},
                "portions": {"dinner": 2},
                "total_stats": {},
                "scores": {},
            }
        ],
        "shopping_list": {},
        "prep_timeline": {"1": []},
        "overall_stats": {},
        "optimization": None,
        "warnings": [],
    }


@pytest.fixture()
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        for user_id, name in [
            (OWNER_ID, "Plan API owner"),
            (VIEWER_ID, "Plan API viewer"),
            (OUTSIDER_ID, "Plan API outsider"),
        ]:
            db.add(
                DBUser(
                    id=user_id,
                    name=name,
                    liked_ingredients=[],
                    disliked_ingredients=[],
                    allergies=[],
                    dietary_restrictions=[],
                    health_conditions=[],
                    medications=[],
                )
            )
        db.add(
            DBHousehold(
                id=HOUSEHOLD_ID,
                owner_user_id=OWNER_ID,
                name="Plan API household",
                timezone="UTC",
                version=1,
            )
        )
        db.flush()
        plan = DBMealPlan(
            user_id=OWNER_ID,
            household_id=HOUSEHOLD_ID,
            schema_version="2",
            plan_data=_plan_payload(),
            status="draft",
            version=1,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        plan_id = plan.id

    identity = {"user_id": OWNER_ID}
    roles = {
        OWNER_ID: HouseholdRole.OWNER,
        VIEWER_ID: HouseholdRole.VIEWER,
    }

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def current_user():
        return SimpleNamespace(id=identity["user_id"])

    def require_access(db, household_id, user_id, minimum_role):
        role = roles.get(user_id)
        if household_id != HOUSEHOLD_ID or role is None:
            raise HTTPException(status_code=404, detail="Resource not found")
        if ROLE_RANK[role] < ROLE_RANK[minimum_role]:
            raise HTTPException(status_code=404, detail="Resource not found")
        return db.get(DBHousehold, HOUSEHOLD_ID), role

    app = FastAPI()
    app.include_router(household_plan_routes.router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = current_user
    original = household_plan_routes.require_household_access
    household_plan_routes.require_household_access = require_access
    try:
        yield TestClient(app), identity, Session, plan_id
    finally:
        household_plan_routes.require_household_access = original


def test_owner_approval_and_viewer_event_history(api):
    client, identity, Session, plan_id = api

    listed = client.get(f"/api/v1/households/{HOUSEHOLD_ID}/plans")
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "draft"
    assert listed.json()[0]["version"] == 1

    approved = client.post(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/approve",
        json={
            "expected_version": 1,
            "reason": "Owner reviewed meals and portions",
            "idempotency_key": "plan-api-approve-0001",
            "metadata": {"source": "api_test"},
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["version"] == 2
    assert approved.json()["approved_by_user_id"] == OWNER_ID
    assert approved.json()["approved_at"] is not None

    identity["user_id"] = VIEWER_ID
    read = client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}"
    )
    assert read.status_code == 200
    assert read.json()["status"] == "approved"

    events = client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/events"
    )
    assert events.status_code == 200
    assert len(events.json()) == 1
    assert events.json()[0]["event_type"] == "approved"
    assert events.json()[0]["from_status"] == "draft"
    assert events.json()[0]["to_status"] == "approved"

    denied = client.post(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/approve",
        json={
            "expected_version": 2,
            "reason": "Viewer must not approve",
            "idempotency_key": "plan-api-viewer-denied",
            "metadata": {},
        },
    )
    assert denied.status_code == 404

    with Session() as db:
        assert db.query(DBHouseholdPlanEvent).count() == 1


def test_outsider_cannot_discover_plan_records(api):
    client, identity, _Session, plan_id = api
    identity["user_id"] = OUTSIDER_ID

    assert client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans"
    ).status_code == 404
    assert client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}"
    ).status_code == 404
    assert client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/events"
    ).status_code == 404
