from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBMealPlan, DBRecipe, DBUser
from backend.domain.approved_plan_preparation import (
    ApprovedPlanPreparationCompileRequest,
)
from backend.domain.preparation_operations import ResourceCalendarVersionCreate
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.approved_plan_preparation_service import (
    compile_approved_plan_preparation,
)
from backend.services.preparation_operations_service import (
    register_resource_calendar,
)


HOUSEHOLD_ID = "empty-profile-home"
OWNER_ID = "empty-profile-owner@example.test"
RECIPE_ID = "empty-profile-recipe"
NOW = datetime(2026, 8, 2, 17, 0, tzinfo=timezone.utc)


def test_empty_reviewed_profile_cannot_compile_as_complete_schedule():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with Session() as db:
        db.add(
            DBUser(
                id=OWNER_ID,
                name="Empty profile owner",
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
                name="Empty profile household",
                timezone="UTC",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        recipe_document = {
            "id": RECIPE_ID,
            "name": "Empty profile recipe",
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
        db.add(
            DBRecipe(
                id=RECIPE_ID,
                name="Empty profile recipe",
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
            recipe_id=RECIPE_ID,
            profile_version="v1",
            schema_version="1",
            supported_servings_min=1,
            supported_servings_max=4,
            task_templates=[],
            source_name="Corrupted empty reviewed fixture",
            source_url="https://example.test/empty-profile",
            source_version="2026-08-02",
            evidence_status="reviewed",
            reviewed_at=NOW,
            reviewed_by="Empty profile reviewer",
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
            plan_data={
                "user_id": OWNER_ID,
                "days": [
                    {
                        "day": 1,
                        "meals": {"Dinner": recipe_document},
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
            },
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
                    "reviewed_by": "Empty profile reviewer",
                    "notes": None,
                    "activate": True,
                    "idempotency_key": "empty-profile-calendar-v1",
                }
            ),
        )
        candidates_endpoint_id = "day-1.dinner-"
        from backend.services.household_plan_occurrence_service import (
            get_approved_plan_occurrence_candidates,
        )

        candidates = get_approved_plan_occurrence_candidates(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan.id,
            expected_version=2,
        )
        occurrence_id = candidates.candidates[0].occurrence_id
        assert occurrence_id.startswith(candidates_endpoint_id)
        payload = ApprovedPlanPreparationCompileRequest.model_validate(
            {
                "expected_plan_version": 2,
                "calendar_version_id": calendar.id,
                "occurrence_set": {
                    "document_version": "preparation-occurrence-set-v1",
                    "household_id": HOUSEHOLD_ID,
                    "occurrence_set_version": "empty-profile-occurrences-v1",
                    "duration_policy": "conservative_max",
                    "occurrences": [
                        {
                            "occurrence_id": occurrence_id,
                            "recipe_id": RECIPE_ID,
                            "required_finish_minute": 180,
                            "servings": 2,
                            "priority": 0,
                        }
                    ],
                },
                "profile_versions": {
                    RECIPE_ID: (
                        f"profile:{profile.id}/version:{profile.profile_version}/"
                        f"sha256:{profile.content_hash}"
                    )
                },
                "granularity_minutes": 5,
            }
        )

        with pytest.raises(HTTPException) as rejected:
            compile_approved_plan_preparation(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=plan.id,
                payload=payload,
            )

    assert rejected.value.status_code == 409
    assert rejected.value.detail["code"] == "reviewed_preparation_profile_empty"
