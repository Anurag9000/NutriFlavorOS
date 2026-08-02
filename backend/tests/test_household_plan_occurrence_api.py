from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import household_plan_routes
from backend.database import (
    Base,
    DBHousehold,
    DBMealPlan,
    DBRecipe,
    DBUser,
    get_db,
)
from backend.domain.household_access import HouseholdRole
from backend.meal_plan_lifecycle_models import DBHouseholdPlanEvent
from backend.preparation_models import DBRecipePreparationProfile
from backend.utils.security import get_current_user


HOUSEHOLD_ID = "occurrence-api-home"
OWNER_ID = "occurrence-api-owner@example.test"
EDITOR_ID = "occurrence-api-editor@example.test"
VIEWER_ID = "occurrence-api-viewer@example.test"
OUTSIDER_ID = "occurrence-api-outsider@example.test"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
ROLE_RANK = {
    HouseholdRole.VIEWER: 1,
    HouseholdRole.EDITOR: 2,
    HouseholdRole.OWNER: 3,
}


def _plan_payload() -> dict:
    recipe = {
        "id": "occurrence-api-recipe",
        "name": "Occurrence API meal",
        "description": "Fixture",
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
                "meals": {"Dinner": recipe},
                "portions": {"Dinner": 2},
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
            (OWNER_ID, "Occurrence API owner"),
            (EDITOR_ID, "Occurrence API editor"),
            (VIEWER_ID, "Occurrence API viewer"),
            (OUTSIDER_ID, "Occurrence API outsider"),
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
                name="Occurrence API household",
                timezone="UTC",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            DBRecipe(
                id="occurrence-api-recipe",
                name="Occurrence API meal",
                description="Fixture",
                ingredients=[],
                ingredient_data=[],
                servings=2,
                calories=400,
                macros={},
                flavor_profile={},
                tags=[],
                instructions=["Cook"],
                estimated_cost=100,
                nutrition_basis="per_serving",
            )
        )
        db.flush()
        db.add(
            DBRecipePreparationProfile(
                recipe_id="occurrence-api-recipe",
                profile_version="v1",
                schema_version="1",
                supported_servings_min=1,
                supported_servings_max=6,
                task_templates=[
                    {
                        "template_id": "cook",
                        "name": "Cook",
                        "duration_min_minutes": 20,
                        "duration_max_minutes": 30,
                        "resource_demands": {"person": 1},
                        "dependencies": [],
                        "active_work": True,
                        "unattended_allowed": False,
                        "notes": None,
                    }
                ],
                source_name="Reviewed occurrence API fixture",
                source_url="https://example.test/occurrence-api",
                source_version="2026-08-02",
                evidence_status="reviewed",
                reviewed_at=NOW,
                reviewed_by="Occurrence API reviewer",
                notes=None,
                content_hash="a" * 64,
                supersedes_profile_id=None,
                active=True,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        plan = DBMealPlan(
            user_id=OWNER_ID,
            household_id=HOUSEHOLD_ID,
            schema_version="2",
            plan_data=_plan_payload(),
            status="approved",
            version=2,
            approved_by_user_id=OWNER_ID,
            approved_at=NOW,
            cancelled_at=None,
            cancellation_reason=None,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        plan_id = plan.id

    identity = {"user_id": VIEWER_ID}
    roles = {
        OWNER_ID: HouseholdRole.OWNER,
        EDITOR_ID: HouseholdRole.EDITOR,
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
        yield TestClient(app), identity, plan_id
    finally:
        household_plan_routes.require_household_access = original


def test_viewer_can_read_candidates_but_cannot_confirm(api):
    client, identity, plan_id = api
    candidates = client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/"
        "preparation-occurrences/candidates?expected_plan_version=2"
    )
    assert candidates.status_code == 200
    body = candidates.json()
    assert body["source_plan_id"] == plan_id
    assert body["source_plan_version"] == 2
    assert body["reviewed_compatible_count"] == 1
    assert body["unresolved_profile_count"] == 0
    assert body["candidates"][0]["source_recipe_servings"] == 2
    assert body["candidates"][0]["planned_servings"] == 2
    assert body["candidates"][0]["recipe_batch_scale"] == 1
    assert "required_finish_minute" not in body["candidates"][0]

    occurrence_id = body["candidates"][0]["occurrence_id"]
    denied = client.post(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/"
        "preparation-occurrences/confirm",
        json={
            "expected_plan_version": 2,
            "occurrence_set_version": "occurrence-api-v1",
            "duration_policy": "conservative_max",
            "confirmations": [
                {
                    "occurrence_id": occurrence_id,
                    "include": True,
                    "servings": 2,
                    "required_finish_minute": 180,
                    "priority": 1,
                }
            ],
        },
    )
    assert denied.status_code == 404

    identity["user_id"] = EDITOR_ID
    confirmed = client.post(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/"
        "preparation-occurrences/confirm",
        json={
            "expected_plan_version": 2,
            "occurrence_set_version": "occurrence-api-v1",
            "duration_policy": "conservative_max",
            "confirmations": [
                {
                    "occurrence_id": occurrence_id,
                    "include": True,
                    "servings": 2,
                    "required_finish_minute": 180,
                    "priority": 1,
                }
            ],
        },
    )
    assert confirmed.status_code == 200
    confirmed_body = confirmed.json()
    assert confirmed_body["confirmed_count"] == 1
    assert confirmed_body["excluded_count"] == 0
    assert confirmed_body["occurrence_set"]["occurrences"][0][
        "required_finish_minute"
    ] == 180
    assert confirmed_body["occurrence_set"]["occurrences"][0][
        "servings"
    ] == 2
    assert confirmed_body["profile_versions"]["occurrence-api-recipe"].startswith(
        "profile:"
    )


def test_stale_and_outsider_candidate_requests_fail_closed(api):
    client, identity, plan_id = api
    stale = client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/"
        "preparation-occurrences/candidates?expected_plan_version=1"
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "source_plan_version_mismatch"

    identity["user_id"] = OUTSIDER_ID
    hidden = client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/"
        "preparation-occurrences/candidates?expected_plan_version=2"
    )
    assert hidden.status_code == 404
