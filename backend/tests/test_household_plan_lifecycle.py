from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import (
    Base,
    DBHousehold,
    DBMealPlan,
    DBStockReservation,
    DBUser,
)
from backend.domain.household_plan_lifecycle import (
    HouseholdPlanEventType,
    HouseholdPlanTransitionRequest,
)
from backend.meal_plan_lifecycle_models import DBHouseholdPlanEvent
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.services.household_plan_lifecycle_service import (
    assert_approved_source_plan,
    list_household_plan_events,
    transition_household_plan,
)


HOUSEHOLD_ID = "plan-lifecycle-home"
OWNER_ID = "plan-owner@example.test"
NOW = datetime(2026, 8, 2, 8, 0, tzinfo=timezone.utc)


def _plan_payload() -> dict:
    recipe = {
        "id": "recipe-1",
        "name": "Reviewed meal",
        "description": "Fixture recipe",
        "ingredients": ["1 cup rice"],
        "ingredient_lines": [],
        "servings": 2,
        "calories": 400,
        "macros": {"protein_g": 10, "carbs_g": 70, "fat_g": 5},
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
                name="Plan owner",
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
                name="Plan lifecycle household",
                timezone="UTC",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.commit()
    return factory


def _create_plan(Session, *, status: str = "draft", version: int = 1) -> int:
    with Session() as db:
        approved = status == "approved"
        plan = DBMealPlan(
            user_id=OWNER_ID,
            household_id=HOUSEHOLD_ID,
            schema_version="2",
            plan_data=_plan_payload(),
            status=status,
            version=version,
            approved_by_user_id=OWNER_ID if approved else None,
            approved_at=NOW if approved else None,
            cancelled_at=None,
            cancellation_reason=None,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan.id


def _transition(
    *,
    expected_version: int,
    reason: str,
    key: str,
) -> HouseholdPlanTransitionRequest:
    return HouseholdPlanTransitionRequest(
        expected_version=expected_version,
        reason=reason,
        idempotency_key=key,
        metadata={"source": "test"},
    )


def test_approve_is_optimistic_idempotent_and_audited(Session):
    plan_id = _create_plan(Session)
    payload = _transition(
        expected_version=1,
        reason="Household reviewed meals and portions",
        key="approve-plan-0001",
    )
    with Session() as db:
        approved = transition_household_plan(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            actor_user_id=OWNER_ID,
            event_type=HouseholdPlanEventType.APPROVED,
            payload=payload,
        )
        assert approved.status.value == "approved"
        assert approved.version == 2
        assert approved.approved_by_user_id == OWNER_ID
        assert approved.approved_at is not None

    with Session() as db:
        retried = transition_household_plan(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            actor_user_id=OWNER_ID,
            event_type=HouseholdPlanEventType.APPROVED,
            payload=payload,
        )
        events = list_household_plan_events(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
        )
        assert retried.version == 2
        assert len(events) == 1
        assert events[0].from_status.value == "draft"
        assert events[0].to_status.value == "approved"

    with Session() as db:
        with pytest.raises(HTTPException) as conflict:
            transition_household_plan(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=plan_id,
                actor_user_id=OWNER_ID,
                event_type=HouseholdPlanEventType.APPROVED,
                payload=_transition(
                    expected_version=1,
                    reason="Different decision under reused key",
                    key="approve-plan-0001",
                ),
            )
        assert conflict.value.status_code == 409
        assert conflict.value.detail["code"] == "plan_transition_idempotency_conflict"


def test_stale_plan_version_fails_closed(Session):
    plan_id = _create_plan(Session)
    with Session() as db:
        with pytest.raises(HTTPException) as stale:
            transition_household_plan(
                db,
                household_id=HOUSEHOLD_ID,
                plan_id=plan_id,
                actor_user_id=OWNER_ID,
                event_type=HouseholdPlanEventType.APPROVED,
                payload=_transition(
                    expected_version=2,
                    reason="Stale approval attempt",
                    key="approve-plan-stale",
                ),
            )
        assert stale.value.status_code == 409
        assert stale.value.detail["code"] == "stale_plan_version"
        assert stale.value.detail["current_version"] == 1


def test_source_plan_requires_exact_approved_version(Session):
    plan_id = _create_plan(Session)
    with Session() as db:
        with pytest.raises(HTTPException) as draft:
            assert_approved_source_plan(
                db,
                household_id=HOUSEHOLD_ID,
                source_plan_id=plan_id,
                source_plan_version=1,
            )
        assert draft.value.detail["code"] == "source_plan_not_approved"

        transition_household_plan(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            actor_user_id=OWNER_ID,
            event_type=HouseholdPlanEventType.APPROVED,
            payload=_transition(
                expected_version=1,
                reason="Approve for preparation occurrence generation",
                key="approve-plan-source",
            ),
        )

    with Session() as db:
        assert_approved_source_plan(
            db,
            household_id=HOUSEHOLD_ID,
            source_plan_id=plan_id,
            source_plan_version=2,
        )
        with pytest.raises(HTTPException) as stale:
            assert_approved_source_plan(
                db,
                household_id=HOUSEHOLD_ID,
                source_plan_id=plan_id,
                source_plan_version=1,
            )
        assert stale.value.detail["code"] == "source_plan_version_mismatch"


def test_cancellation_releases_reservations_and_invalidates_schedules(Session):
    plan_id = _create_plan(Session, status="approved", version=2)
    with Session() as db:
        calendar = DBResourceCalendarVersion(
            household_id=HOUSEHOLD_ID,
            calendar_version="calendar-v1",
            horizon_minutes=240,
            timezone="UTC",
            evidence_status="reviewed",
            reviewed_at=NOW,
            reviewed_by="Plan owner",
            notes=None,
            content_hash="a" * 64,
            supersedes_calendar_id=None,
            active=True,
            created_by_user_id=OWNER_ID,
            idempotency_key="calendar-plan-lifecycle",
            request_fingerprint="b" * 64,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(calendar)
        db.flush()
        reservation = DBStockReservation(
            household_id=HOUSEHOLD_ID,
            pantry_item_id=None,
            plan_id=plan_id,
            canonical_name="rice",
            quantity_min=1,
            quantity_max=1,
            unit="cup",
            status="active",
            expires_at=NOW + timedelta(hours=4),
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
        schedule = DBPersistedPreparationSchedule(
            household_id=HOUSEHOLD_ID,
            calendar_version_id=calendar.id,
            calendar_content_hash=calendar.content_hash,
            source_plan_id=plan_id,
            source_plan_version=2,
            occurrence_set_version="occurrences-v1",
            occurrence_set_hash="c" * 64,
            occurrence_set_payload=None,
            profile_versions={},
            schedule_request_payload=None,
            schedule_request_hash=None,
            schedule_payload={
                "method": "fixture",
                "deterministic": True,
                "horizon_minutes": 240,
                "granularity_minutes": 5,
                "scheduled": [],
                "unscheduled": [],
                "resource_utilization": {},
                "resource_peak_usage": {},
                "makespan_minutes": 0,
                "diagnostics": {},
            },
            schedule_hash="d" * 64,
            status="approved",
            version=1,
            notes=None,
            created_by_user_id=OWNER_ID,
            approved_by_user_id=OWNER_ID,
            approved_at=NOW,
            invalidated_at=None,
            invalidation_reason=None,
            creation_idempotency_key="schedule-plan-lifecycle",
            creation_request_fingerprint="e" * 64,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add_all([reservation, schedule])
        db.commit()
        schedule_id = schedule.id
        reservation_id = reservation.id

    payload = _transition(
        expected_version=2,
        reason="Household cancelled the approved meal plan",
        key="cancel-plan-0001",
    )
    with Session() as db:
        cancelled = transition_household_plan(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            actor_user_id=OWNER_ID,
            event_type=HouseholdPlanEventType.CANCELLED,
            payload=payload,
        )
        assert cancelled.status.value == "cancelled"
        assert cancelled.version == 3
        assert cancelled.cancellation_reason == payload.reason

    with Session() as db:
        reservation = db.get(DBStockReservation, reservation_id)
        schedule = db.get(DBPersistedPreparationSchedule, schedule_id)
        plan_events = db.query(DBHouseholdPlanEvent).all()
        schedule_events = db.query(DBPreparationScheduleEvent).all()

        assert reservation.status == "released"
        assert reservation.version == 2
        assert schedule.status == "invalidated"
        assert schedule.version == 2
        assert "Source household plan" in schedule.invalidation_reason
        assert len(plan_events) == 1
        assert plan_events[0].event_metadata["released_reservation_count"] == 1
        assert (
            plan_events[0].event_metadata[
                "invalidated_preparation_schedule_count"
            ]
            == 1
        )
        assert len(schedule_events) == 1
        assert schedule_events[0].event_type == "invalidated"
        assert schedule_events[0].event_metadata["source_plan_event"] == "cancelled"

        with pytest.raises(HTTPException) as cancelled_source:
            assert_approved_source_plan(
                db,
                household_id=HOUSEHOLD_ID,
                source_plan_id=plan_id,
                source_plan_version=2,
            )
        assert cancelled_source.value.detail["code"] == "source_plan_version_mismatch"
