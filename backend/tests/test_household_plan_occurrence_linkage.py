from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBMealPlan, DBRecipe, DBUser
from backend.domain.preparation_operations import PreparationOccurrenceSetDocument
from backend.services.household_plan_occurrence_service import (
    get_approved_plan_occurrence_candidates,
    validate_occurrence_set_against_approved_plan,
)


HOUSEHOLD_ID = "occurrence-link-home"
OWNER_ID = "occurrence-link-owner@example.test"
NOW = datetime(2026, 8, 2, 16, 0, tzinfo=timezone.utc)


def _recipe(recipe_id: str, name: str) -> dict:
    return {
        "id": recipe_id,
        "name": name,
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
                name="Occurrence link owner",
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
                name="Occurrence link household",
                timezone="UTC",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add_all(
            [
                DBRecipe(
                    id="recipe-planned",
                    name="Planned meal",
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
                    id="recipe-injected",
                    name="Injected meal",
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
            ]
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
                        "meals": {"Dinner": _recipe("recipe-planned", "Planned meal")},
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
        db.add(plan)
        db.commit()
        db.refresh(plan)
        plan_id = plan.id
    return factory, plan_id


def _document(occurrence_id: str, recipe_id: str) -> PreparationOccurrenceSetDocument:
    return PreparationOccurrenceSetDocument.model_validate(
        {
            "document_version": "preparation-occurrence-set-v1",
            "household_id": HOUSEHOLD_ID,
            "occurrence_set_version": "occurrence-link-v1",
            "duration_policy": "conservative_max",
            "occurrences": [
                {
                    "occurrence_id": occurrence_id,
                    "recipe_id": recipe_id,
                    "required_finish_minute": 180,
                    "servings": 2,
                    "priority": 0,
                }
            ],
        }
    )


def test_exact_occurrence_and_recipe_linkage_passes(Session):
    factory, plan_id = Session
    with factory() as db:
        candidates = get_approved_plan_occurrence_candidates(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            expected_version=2,
        )
        candidate = candidates.candidates[0]
        validated = validate_occurrence_set_against_approved_plan(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            expected_version=2,
            occurrence_set=_document(
                candidate.occurrence_id,
                candidate.recipe_id,
            ),
            lock=False,
        )
    assert validated.source_plan_id == plan_id
    assert validated.source_plan_version == 2


def test_injected_occurrence_id_fails_closed(Session):
    factory, plan_id = Session
    with factory() as db:
        with pytest.raises(HTTPException) as injected:
            validate_occurrence_set_against_approved_plan(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=plan_id,
                expected_version=2,
                occurrence_set=_document(
                    "day-99.injected",
                    "recipe-injected",
                ),
                lock=False,
            )
    assert injected.value.status_code == 409
    assert injected.value.detail["code"] == "occurrence_source_plan_mismatch"
    assert injected.value.detail["unknown_occurrence_ids"] == [
        "day-99.injected"
    ]


def test_recipe_substitution_for_valid_occurrence_id_fails_closed(Session):
    factory, plan_id = Session
    with factory() as db:
        candidates = get_approved_plan_occurrence_candidates(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            expected_version=2,
        )
        candidate = candidates.candidates[0]
        with pytest.raises(HTTPException) as substitution:
            validate_occurrence_set_against_approved_plan(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=plan_id,
                expected_version=2,
                occurrence_set=_document(
                    candidate.occurrence_id,
                    "recipe-injected",
                ),
                lock=False,
            )
    assert substitution.value.status_code == 409
    assert substitution.value.detail["code"] == "occurrence_source_plan_mismatch"
    assert substitution.value.detail["recipe_mismatches"] == [
        {
            "occurrence_id": candidate.occurrence_id,
            "expected_recipe_id": "recipe-planned",
            "submitted_recipe_id": "recipe-injected",
        }
    ]
