#!/usr/bin/env python3
"""PostgreSQL concurrency probe for household meal-plan lifecycle transitions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Callable

from backend.database import (
    DBHousehold,
    DBMealPlan,
    DBStockReservation,
    DBUser,
    SessionLocal,
)
from backend.domain.household_plan_lifecycle import (
    HouseholdPlanEventType,
    HouseholdPlanTransitionRequest,
)
from backend.meal_plan_lifecycle_models import DBHouseholdPlanEvent
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.services.household_plan_lifecycle_service import (
    transition_household_plan,
)


USER_ID = "ci-household-plan@example.test"
HOUSEHOLD_ID = "ci-household-plan-home"


def _run_pair(left: Callable[[], object], right: Callable[[], object]):
    barrier = Barrier(2)

    def execute(label: str, callback: Callable[[], object]):
        barrier.wait(timeout=10)
        try:
            return label, callback()
        except Exception as exc:  # Deliberately captured for race assertions.
            return label, exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(execute, "left", left),
            pool.submit(execute, "right", right),
        ]
        return [future.result(timeout=45) for future in futures]


def _plan_payload() -> dict:
    recipe = {
        "id": "ci-plan-recipe",
        "name": "CI plan recipe",
        "description": "Concurrency fixture",
        "ingredients": [],
        "ingredient_lines": [],
        "servings": 2.0,
        "calories": 400,
        "macros": {},
        "flavor_profile": {},
        "tags": [],
        "instructions": ["Cook"],
        "estimated_cost": 100.0,
        "nutrition_basis": "per_serving",
    }
    return {
        "user_id": USER_ID,
        "days": [
            {
                "day": 1,
                "meals": {"dinner": recipe},
                "portions": {"dinner": 2.0},
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


def _reset() -> None:
    with SessionLocal() as db:
        db.query(DBPreparationScheduleEvent).filter(
            DBPreparationScheduleEvent.household_id == HOUSEHOLD_ID
        ).delete(synchronize_session=False)
        db.query(DBPersistedPreparationSchedule).filter(
            DBPersistedPreparationSchedule.household_id == HOUSEHOLD_ID
        ).delete(synchronize_session=False)
        db.query(DBHouseholdPlanEvent).filter(
            DBHouseholdPlanEvent.household_id == HOUSEHOLD_ID
        ).delete(synchronize_session=False)
        db.query(DBStockReservation).filter(
            DBStockReservation.household_id == HOUSEHOLD_ID
        ).delete(synchronize_session=False)
        db.query(DBMealPlan).filter(
            DBMealPlan.household_id == HOUSEHOLD_ID
        ).delete(synchronize_session=False)
        db.query(DBHousehold).filter(DBHousehold.id == HOUSEHOLD_ID).delete(
            synchronize_session=False
        )
        db.query(DBUser).filter(DBUser.id == USER_ID).delete(
            synchronize_session=False
        )
        db.commit()


def _seed_plan() -> int:
    with SessionLocal() as db:
        db.add(
            DBUser(
                id=USER_ID,
                name="CI household plan",
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
                owner_user_id=USER_ID,
                name="CI household plan",
                timezone="UTC",
                version=1,
            )
        )
        db.flush()
        plan = DBMealPlan(
            user_id=USER_ID,
            household_id=HOUSEHOLD_ID,
            schema_version="2",
            plan_data=_plan_payload(),
            status="draft",
            version=1,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan.id


def _transition(
    plan_id: int,
    event_type: HouseholdPlanEventType,
    key: str,
):
    with SessionLocal() as db:
        return transition_household_plan(
            db,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            actor_user_id=USER_ID,
            event_type=event_type,
            payload=HouseholdPlanTransitionRequest.model_validate(
                {
                    "expected_version": 1,
                    "reason": f"CI concurrent {event_type.value}",
                    "idempotency_key": key,
                    "metadata": {"probe": "postgresql"},
                }
            ),
        )


def _assert_identical_approval_retry_collapses() -> None:
    plan_id = _seed_plan()
    results = _run_pair(
        lambda: _transition(
            plan_id,
            HouseholdPlanEventType.APPROVED,
            "ci-plan-identical-approve",
        ),
        lambda: _transition(
            plan_id,
            HouseholdPlanEventType.APPROVED,
            "ci-plan-identical-approve",
        ),
    )
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    assert {value.version for _, value in results} == {2}
    assert {value.status.value for _, value in results} == {"approved"}
    with SessionLocal() as db:
        row = db.get(DBMealPlan, plan_id)
        events = db.query(DBHouseholdPlanEvent).filter(
            DBHouseholdPlanEvent.plan_id == plan_id
        ).all()
        assert row.status == "approved"
        assert row.version == 2
        assert len(events) == 1


def _assert_competing_approval_and_cancellation_have_one_winner() -> None:
    plan_id = _seed_plan()
    results = _run_pair(
        lambda: _transition(
            plan_id,
            HouseholdPlanEventType.APPROVED,
            "ci-plan-race-approve",
        ),
        lambda: _transition(
            plan_id,
            HouseholdPlanEventType.CANCELLED,
            "ci-plan-race-cancel",
        ),
    )
    successes = [value for _, value in results if not isinstance(value, Exception)]
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert len(successes) == 1, results
    assert len(errors) == 1, results
    with SessionLocal() as db:
        row = db.get(DBMealPlan, plan_id)
        events = db.query(DBHouseholdPlanEvent).filter(
            DBHouseholdPlanEvent.plan_id == plan_id
        ).all()
        assert row.status in {"approved", "cancelled"}
        assert row.version == 2
        assert len(events) == 1
        assert events[0].to_status == row.status


def main() -> int:
    _reset()
    try:
        _assert_identical_approval_retry_collapses()
        _reset()
        _assert_competing_approval_and_cancellation_have_one_winner()
        print("Household plan PostgreSQL concurrency probe passed")
        return 0
    finally:
        _reset()


if __name__ == "__main__":
    raise SystemExit(main())
