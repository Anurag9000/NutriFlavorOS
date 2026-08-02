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
from backend.domain.preparation_operations import ResourceCalendarVersionCreate
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.preparation_operations_service import (
    register_resource_calendar,
)
from backend.utils.security import get_current_user


HOUSEHOLD_ID = "approved-compile-api-home"
OWNER_ID = "approved-compile-api-owner@example.test"
EDITOR_ID = "approved-compile-api-editor@example.test"
VIEWER_ID = "approved-compile-api-viewer@example.test"
OUTSIDER_ID = "approved-compile-api-outsider@example.test"
NOW = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
ROLE_RANK = {
    HouseholdRole.VIEWER: 1,
    HouseholdRole.EDITOR: 2,
    HouseholdRole.OWNER: 3,
}


def _recipe_document() -> dict:
    return {
        "id": "approved-compile-api-recipe",
        "name": "Approved compile API meal",
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


def _plan_document() -> dict:
    return {
        "user_id": OWNER_ID,
        "days": [
            {
                "day": 1,
                "meals": {"Dinner": _recipe_document()},
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
            (OWNER_ID, "Approved compile API owner"),
            (EDITOR_ID, "Approved compile API editor"),
            (VIEWER_ID, "Approved compile API viewer"),
            (OUTSIDER_ID, "Approved compile API outsider"),
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
                name="Approved compile API household",
                timezone="UTC",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            DBRecipe(
                id="approved-compile-api-recipe",
                name="Approved compile API meal",
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
        profile = DBRecipePreparationProfile(
            recipe_id="approved-compile-api-recipe",
            profile_version="v1",
            schema_version="1",
            supported_servings_min=1,
            supported_servings_max=4,
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
            source_name="Reviewed approved compile API fixture",
            source_url="https://example.test/approved-compile-api",
            source_version="2026-08-02",
            evidence_status="reviewed",
            reviewed_at=NOW,
            reviewed_by="Approved compile API reviewer",
            notes=None,
            content_hash="a" * 64,
            supersedes_profile_id=None,
            active=True,
            created_at=NOW,
            updated_at=NOW,
        )
        plan = DBMealPlan(
            user_id=OWNER_ID,
            household_id=HOUSEHOLD_ID,
            schema_version="2",
            plan_data=_plan_document(),
            status="approved",
            version=2,
            approved_by_user_id=OWNER_ID,
            approved_at=NOW,
            cancelled_at=None,
            cancellation_reason=None,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add_all([profile, plan])
        db.commit()
        db.refresh(profile)
        db.refresh(plan)
        profile_identity = (
            f"profile:{profile.id}/version:{profile.profile_version}/"
            f"sha256:{profile.content_hash}"
        )
        plan_id = plan.id

        calendar = register_resource_calendar(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=ResourceCalendarVersionCreate.model_validate(
                {
                    "calendar_version": "calendar-v1",
                    "horizon_minutes": 240,
                    "timezone": "UTC",
                    "resources": [
                        {
                            "resource_id": "person",
                            "label": "Available cook",
                            "capacity": 1,
                            "resource_kind": "person",
                            "availability_windows": [
                                {"start_minute": 0, "end_minute": 240}
                            ],
                            "metadata": {},
                        }
                    ],
                    "evidence_status": "reviewed",
                    "reviewed_at": NOW,
                    "reviewed_by": "Approved compile API reviewer",
                    "notes": None,
                    "activate": True,
                    "idempotency_key": "approved-compile-api-calendar-v1",
                }
            ),
        )
        calendar_id = calendar.id

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
        yield (
            TestClient(app),
            identity,
            plan_id,
            calendar_id,
            profile_identity,
        )
    finally:
        household_plan_routes.require_household_access = original


def _payload(calendar_id: int, profile_identity: str) -> dict:
    return {
        "expected_plan_version": 2,
        "calendar_version_id": calendar_id,
        "occurrence_set": {
            "document_version": "preparation-occurrence-set-v1",
            "household_id": HOUSEHOLD_ID,
            "occurrence_set_version": "approved-compile-api-occurrences-v1",
            "duration_policy": "conservative_max",
            "occurrences": [
                {
                    "occurrence_id": "day-1.dinner",
                    "recipe_id": "approved-compile-api-recipe",
                    "required_finish_minute": 180,
                    "servings": 2,
                    "priority": 1,
                }
            ],
        },
        "profile_versions": {
            "approved-compile-api-recipe": profile_identity,
        },
        "granularity_minutes": 5,
    }


def test_viewer_cannot_compile_but_editor_can(api):
    client, identity, plan_id, calendar_id, profile_identity = api
    endpoint = (
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/"
        "preparation-occurrences/compile"
    )

    denied = client.post(endpoint, json=_payload(calendar_id, profile_identity))
    assert denied.status_code == 404

    identity["user_id"] = EDITOR_ID
    compiled = client.post(endpoint, json=_payload(calendar_id, profile_identity))
    assert compiled.status_code == 200
    body = compiled.json()
    assert body["household_id"] == HOUSEHOLD_ID
    assert body["source_plan_id"] == plan_id
    assert body["source_plan_version"] == 2
    assert body["calendar_version_id"] == calendar_id
    assert body["partial"] is False
    assert body["execution_status"] == "complete"
    assert len(body["schedule_request"]["tasks"]) == 1
    assert len(body["schedule_response"]["scheduled"]) == 1
    assert body["schedule_response"]["unscheduled"] == []


def test_stale_profile_and_outsider_requests_fail_closed(api):
    client, identity, plan_id, calendar_id, profile_identity = api
    identity["user_id"] = EDITOR_ID
    endpoint = (
        f"/api/v1/households/{HOUSEHOLD_ID}/plans/{plan_id}/"
        "preparation-occurrences/compile"
    )

    stale = _payload(calendar_id, profile_identity)
    stale["expected_plan_version"] = 1
    stale_response = client.post(endpoint, json=stale)
    assert stale_response.status_code == 409
    assert stale_response.json()["detail"]["code"] == (
        "source_plan_version_mismatch"
    )

    drift = _payload(calendar_id, profile_identity[:-64] + ("b" * 64))
    drift_response = client.post(endpoint, json=drift)
    assert drift_response.status_code == 409
    assert drift_response.json()["detail"]["code"] == (
        "preparation_profile_version_mismatch"
    )

    identity["user_id"] = OUTSIDER_ID
    hidden = client.post(endpoint, json=_payload(calendar_id, profile_identity))
    assert hidden.status_code == 404
