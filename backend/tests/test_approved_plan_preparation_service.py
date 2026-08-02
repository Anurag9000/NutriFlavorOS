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
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBResourceCalendarVersion,
)
from backend.services.approved_plan_preparation_service import (
    compile_approved_plan_preparation,
)
from backend.services.preparation_operations_service import (
    register_resource_calendar,
)


HOUSEHOLD_ID = "approved-compile-home"
OWNER_ID = "approved-compile-owner@example.test"
NOW = datetime(2026, 8, 2, 14, 0, tzinfo=timezone.utc)
PROFILE_HASH = "a" * 64


def _recipe_document() -> dict:
    return {
        "id": "approved-compile-recipe",
        "name": "Approved compile meal",
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


def _plan_payload() -> dict:
    return {
        "user_id": OWNER_ID,
        "days": [
            {
                "day": 1,
                "meals": {"dinner": _recipe_document()},
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
                name="Approved compile owner",
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
                name="Approved compile household",
                timezone="UTC",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            DBRecipe(
                id="approved-compile-recipe",
                name="Approved compile meal",
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
                recipe_id="approved-compile-recipe",
                profile_version="v1",
                schema_version="1",
                supported_servings_min=1,
                supported_servings_max=6,
                task_templates=[
                    {
                        "template_id": "prep",
                        "name": "Prepare",
                        "duration_min_minutes": 10,
                        "duration_max_minutes": 15,
                        "resource_demands": {"person": 1},
                        "dependencies": [],
                        "active_work": True,
                        "unattended_allowed": False,
                        "notes": None,
                    },
                    {
                        "template_id": "cook",
                        "name": "Cook",
                        "duration_min_minutes": 20,
                        "duration_max_minutes": 30,
                        "resource_demands": {"person": 1, "burner": 1},
                        "dependencies": ["prep"],
                        "active_work": True,
                        "unattended_allowed": False,
                        "notes": None,
                    },
                ],
                source_name="Reviewed compile fixture",
                source_url="https://example.test/approved-compile",
                source_version="2026-08-02",
                evidence_status="reviewed",
                reviewed_at=NOW,
                reviewed_by="Approved compile reviewer",
                notes=None,
                content_hash=PROFILE_HASH,
                supersedes_profile_id=None,
                active=True,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            DBMealPlan(
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
        )
        db.commit()
    return factory


def _register_calendar(
    Session,
    *,
    version: str = "calendar-v1",
    person_end: int = 240,
    include_burner: bool = True,
) -> int:
    resources = [
        {
            "resource_id": "person",
            "label": "Available cook",
            "capacity": 1,
            "resource_kind": "person",
            "availability_windows": [
                {"start_minute": 0, "end_minute": person_end}
            ],
            "metadata": {"fixture": True},
        }
    ]
    if include_burner:
        resources.append(
            {
                "resource_id": "burner",
                "label": "Stove burner",
                "capacity": 1,
                "resource_kind": "equipment",
                "availability_windows": [
                    {"start_minute": 0, "end_minute": 240}
                ],
                "metadata": {"fixture": True},
            }
        )
    with Session() as db:
        calendar = register_resource_calendar(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=ResourceCalendarVersionCreate.model_validate(
                {
                    "calendar_version": version,
                    "horizon_minutes": 240,
                    "timezone": "UTC",
                    "resources": resources,
                    "evidence_status": "reviewed",
                    "reviewed_at": NOW,
                    "reviewed_by": "Approved compile reviewer",
                    "notes": "Fixture calendar",
                    "activate": True,
                    "idempotency_key": f"approved-compile-{version}",
                }
            ),
        )
        return calendar.id


def _payload(
    calendar_id: int,
    *,
    duration_policy: str = "conservative_max",
    content_hash: str = PROFILE_HASH,
) -> ApprovedPlanPreparationCompileRequest:
    return ApprovedPlanPreparationCompileRequest.model_validate(
        {
            "expected_plan_version": 2,
            "calendar_version_id": calendar_id,
            "occurrence_set": {
                "document_version": "preparation-occurrence-set-v1",
                "household_id": HOUSEHOLD_ID,
                "occurrence_set_version": "plan-1-v2-occurrences-v1",
                "duration_policy": duration_policy,
                "occurrences": [
                    {
                        "occurrence_id": "day-1.dinner",
                        "recipe_id": "approved-compile-recipe",
                        "required_finish_minute": 180,
                        "servings": 2,
                        "priority": 3,
                    }
                ],
            },
            "profile_versions": {
                "approved-compile-recipe": (
                    f"profile:1/version:v1/sha256:{content_hash}"
                )
            },
            "granularity_minutes": 5,
        }
    )


def _plan_id(Session) -> int:
    with Session() as db:
        return db.query(DBMealPlan.id).scalar()


def test_compiles_exact_approved_plan_against_active_calendar(Session):
    calendar_id = _register_calendar(Session)
    with Session() as db:
        result = compile_approved_plan_preparation(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=_plan_id(Session),
            payload=_payload(calendar_id),
        )
        assert db.query(DBPersistedPreparationSchedule).count() == 0

    assert result.source_plan_version == 2
    assert result.calendar_version_id == calendar_id
    assert result.execution_status == "complete"
    assert result.partial is False
    assert result.schedule_response.unscheduled == []
    assert [value.duration_minutes for value in result.schedule_response.scheduled] == [
        15,
        30,
    ]
    assert result.schedule_response.scheduled[1].dependencies == [
        result.schedule_response.scheduled[0].task_id
    ]
    assert result.schedule_request.tasks[1].metadata["profile_content_hash"] == (
        PROFILE_HASH
    )
    assert result.schedule_request.tasks[1].metadata["duration_policy"] == (
        "conservative_max"
    )


def test_optimistic_duration_policy_uses_reviewed_minimums(Session):
    calendar_id = _register_calendar(Session)
    with Session() as db:
        result = compile_approved_plan_preparation(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=_plan_id(Session),
            payload=_payload(calendar_id, duration_policy="optimistic_min"),
        )
    assert [value.duration_minutes for value in result.schedule_response.scheduled] == [
        10,
        20,
    ]


def test_profile_identity_drift_fails_closed(Session):
    calendar_id = _register_calendar(Session)
    with Session() as db:
        with pytest.raises(HTTPException) as drift:
            compile_approved_plan_preparation(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=_plan_id(Session),
                payload=_payload(calendar_id, content_hash="b" * 64),
            )
    assert drift.value.status_code == 409
    assert drift.value.detail["code"] == "preparation_profile_version_mismatch"


def test_stale_plan_and_inactive_calendar_fail_closed(Session):
    calendar_id = _register_calendar(Session)
    stale_payload = _payload(calendar_id)
    stale_payload.expected_plan_version = 1
    with Session() as db:
        with pytest.raises(HTTPException) as stale:
            compile_approved_plan_preparation(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=_plan_id(Session),
                payload=stale_payload,
            )
    assert stale.value.detail["code"] == "source_plan_version_mismatch"

    successor_id = _register_calendar(Session, version="calendar-v2")
    assert successor_id != calendar_id
    with Session() as db:
        with pytest.raises(HTTPException) as inactive:
            compile_approved_plan_preparation(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=_plan_id(Session),
                payload=_payload(calendar_id),
            )
    assert inactive.value.detail["code"] == "resource_calendar_not_active_reviewed"


def test_unscheduled_work_remains_explicit_and_nonpersisted(Session):
    calendar_id = _register_calendar(
        Session,
        person_end=20,
        include_burner=False,
    )
    with Session() as db:
        result = compile_approved_plan_preparation(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=_plan_id(Session),
            payload=_payload(calendar_id),
        )
        assert db.query(DBPersistedPreparationSchedule).count() == 0

    assert result.partial is True
    assert result.execution_status == "partial_unscheduled"
    assert len(result.schedule_response.unscheduled) >= 1
    assert any("Unscheduled work remains" in value for value in result.warnings)
