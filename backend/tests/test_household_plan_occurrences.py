from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBMealPlan, DBRecipe, DBUser
from backend.domain.household_plan_occurrences import (
    ConfirmPlanOccurrenceSetRequest,
)
from backend.meal_plan_lifecycle_models import DBHouseholdPlanEvent
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.household_plan_occurrence_service import (
    confirm_approved_plan_occurrence_set,
    get_approved_plan_occurrence_candidates,
)


HOUSEHOLD_ID = "occurrence-home"
OWNER_ID = "occurrence-owner@example.test"
NOW = datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)
PROFILE_HASH = "a" * 64


def _recipe_document(recipe_id: str, name: str, servings: float) -> dict:
    return {
        "id": recipe_id,
        "name": name,
        "description": "Occurrence fixture",
        "ingredients": [],
        "ingredient_lines": [],
        "servings": servings,
        "calories": 400,
        "macros": {},
        "flavor_profile": {},
        "tags": [],
        "instructions": ["Cook"],
        "estimated_cost": 100,
        "nutrition_basis": "per_serving",
    }


def _plan_payload() -> dict:
    return {
        "user_id": OWNER_ID,
        "days": [
            {
                "day": 1,
                "meals": {
                    "dinner": _recipe_document(
                        "recipe-compatible",
                        "Compatible dinner",
                        2,
                    ),
                    "late snack": _recipe_document(
                        "recipe-missing-profile",
                        "Unprofiled snack",
                        1,
                    ),
                },
                "portions": {
                    "dinner": 2,
                    "late snack": 1,
                },
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
def Session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        db.add(
            DBUser(
                id=OWNER_ID,
                name="Occurrence owner",
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
                name="Occurrence household",
                timezone="UTC",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add_all(
            [
                DBRecipe(
                    id="recipe-compatible",
                    name="Compatible dinner",
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
                ),
                DBRecipe(
                    id="recipe-missing-profile",
                    name="Unprofiled snack",
                    description="Fixture",
                    ingredients=[],
                    ingredient_data=[],
                    servings=1,
                    calories=100,
                    macros={},
                    flavor_profile={},
                    tags=[],
                    instructions=["Assemble"],
                    estimated_cost=20,
                    nutrition_basis="per_serving",
                ),
            ]
        )
        db.flush()
        db.add(
            DBRecipePreparationProfile(
                recipe_id="recipe-compatible",
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
                source_name="Reviewed fixture",
                source_url="https://example.test/preparation",
                source_version="2026-08-02",
                evidence_status="reviewed",
                reviewed_at=NOW,
                reviewed_by="Occurrence reviewer",
                notes=None,
                content_hash=PROFILE_HASH,
                supersedes_profile_id=None,
                active=True,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.commit()
    return factory


def _create_plan(Session, *, status: str = "approved", version: int = 2) -> int:
    with Session() as db:
        plan = DBMealPlan(
            user_id=OWNER_ID,
            household_id=HOUSEHOLD_ID,
            schema_version="2",
            plan_data=_plan_payload(),
            status=status,
            version=version,
            approved_by_user_id=OWNER_ID if status == "approved" else None,
            approved_at=NOW if status == "approved" else None,
            cancelled_at=None,
            cancellation_reason=None,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan.id


def test_candidates_derive_servings_but_not_deadlines(Session):
    plan_id = _create_plan(Session)
    with Session() as db:
        result = get_approved_plan_occurrence_candidates(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            expected_version=2,
        )

    assert result.source_plan_id == plan_id
    assert result.source_plan_version == 2
    assert len(result.candidates) == 2
    assert result.reviewed_compatible_count == 1
    assert result.unresolved_profile_count == 1

    dinner = next(
        value for value in result.candidates if value.meal_slot == "dinner"
    )
    assert dinner.source_recipe_servings == 2
    assert dinner.planned_portion_multiplier == 2
    assert dinner.planned_servings == 4
    assert dinner.preparation_profile_status.value == "reviewed_compatible"
    assert dinner.preparation_profile_id is not None
    assert dinner.supported_servings_min == 1
    assert dinner.supported_servings_max == 6
    assert "required_finish_minute" not in dinner.model_dump(mode="json")

    snack = next(
        value for value in result.candidates if value.meal_slot == "late snack"
    )
    assert snack.preparation_profile_status.value == "missing_reviewed_profile"
    assert snack.preparation_profile_id is None
    assert any("must be entered explicitly" in value for value in result.warnings)


def test_draft_and_stale_plans_fail_closed(Session):
    draft_id = _create_plan(Session, status="draft", version=1)
    with Session() as db:
        with pytest.raises(HTTPException) as draft:
            get_approved_plan_occurrence_candidates(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=draft_id,
                expected_version=1,
            )
        assert draft.value.detail["code"] == "source_plan_not_approved"

    approved_id = _create_plan(Session, status="approved", version=2)
    with Session() as db:
        with pytest.raises(HTTPException) as stale:
            get_approved_plan_occurrence_candidates(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=approved_id,
                expected_version=1,
            )
        assert stale.value.detail["code"] == "source_plan_version_mismatch"


def test_confirmation_requires_explicit_decision_for_every_candidate(Session):
    plan_id = _create_plan(Session)
    with Session() as db:
        candidates = get_approved_plan_occurrence_candidates(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            expected_version=2,
        )
        dinner = next(
            value for value in candidates.candidates if value.meal_slot == "dinner"
        )
        with pytest.raises(HTTPException) as mismatch:
            confirm_approved_plan_occurrence_set(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=plan_id,
                payload=ConfirmPlanOccurrenceSetRequest.model_validate(
                    {
                        "expected_plan_version": 2,
                        "occurrence_set_version": "plan-2-occurrences-v1",
                        "duration_policy": "conservative_max",
                        "confirmations": [
                            {
                                "occurrence_id": dinner.occurrence_id,
                                "include": True,
                                "servings": 4,
                                "required_finish_minute": 180,
                                "priority": 1,
                            }
                        ],
                    }
                ),
            )
        assert mismatch.value.status_code == 422
        assert mismatch.value.detail["code"] == "occurrence_confirmation_set_mismatch"
        assert len(mismatch.value.detail["missing_occurrence_ids"]) == 1


def test_confirmation_rechecks_serving_compatibility(Session):
    plan_id = _create_plan(Session)
    with Session() as db:
        candidates = get_approved_plan_occurrence_candidates(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            expected_version=2,
        )
        confirmations = []
        for value in candidates.candidates:
            confirmations.append(
                {
                    "occurrence_id": value.occurrence_id,
                    "include": value.meal_slot == "dinner",
                    "servings": 10 if value.meal_slot == "dinner" else None,
                    "required_finish_minute": (
                        180 if value.meal_slot == "dinner" else None
                    ),
                    "priority": 1,
                }
            )
        with pytest.raises(HTTPException) as incompatible:
            confirm_approved_plan_occurrence_set(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=plan_id,
                payload=ConfirmPlanOccurrenceSetRequest.model_validate(
                    {
                        "expected_plan_version": 2,
                        "occurrence_set_version": "plan-2-occurrences-v1",
                        "duration_policy": "conservative_max",
                        "confirmations": confirmations,
                    }
                ),
            )
        assert incompatible.value.status_code == 409
        assert incompatible.value.detail["code"] == (
            "confirmed_occurrence_profile_unavailable"
        )
        assert incompatible.value.detail["unresolved"][0][
            "reason_code"
        ] == "reviewed_incompatible_servings"


def test_confirmation_returns_canonical_nonpersisted_document(Session):
    plan_id = _create_plan(Session)
    with Session() as db:
        candidates = get_approved_plan_occurrence_candidates(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            expected_version=2,
        )
        confirmations = []
        for value in candidates.candidates:
            confirmations.append(
                {
                    "occurrence_id": value.occurrence_id,
                    "include": value.meal_slot == "dinner",
                    "servings": 4 if value.meal_slot == "dinner" else None,
                    "required_finish_minute": (
                        180 if value.meal_slot == "dinner" else None
                    ),
                    "priority": 3,
                }
            )
        result = confirm_approved_plan_occurrence_set(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            payload=ConfirmPlanOccurrenceSetRequest.model_validate(
                {
                    "expected_plan_version": 2,
                    "occurrence_set_version": "plan-2-occurrences-v1",
                    "duration_policy": "conservative_max",
                    "confirmations": confirmations,
                }
            ),
        )

    assert result.source_plan_id == plan_id
    assert result.source_plan_version == 2
    assert result.confirmed_count == 1
    assert result.excluded_count == 1
    assert result.occurrence_set.household_id == HOUSEHOLD_ID
    assert result.occurrence_set.occurrence_set_version == "plan-2-occurrences-v1"
    assert len(result.occurrence_set.occurrences) == 1
    occurrence = result.occurrence_set.occurrences[0]
    assert occurrence.recipe_id == "recipe-compatible"
    assert occurrence.servings == 4
    assert occurrence.required_finish_minute == 180
    assert occurrence.priority == 3
    assert result.profile_versions == {
        "recipe-compatible": (
            f"profile:1/version:v1/sha256:{PROFILE_HASH}"
        )
    }
    assert db.query(DBHouseholdPlanEvent).count() == 0
