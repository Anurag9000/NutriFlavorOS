from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from backend.database import DBMealPlan
from backend.domain.household_plan_lifecycle import (
    HouseholdPlanEventType,
    HouseholdPlanTransitionRequest,
)
from backend.meal_plan_lifecycle_models import DBHouseholdPlanEvent
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.household_plan_lifecycle_service import (
    transition_household_plan,
)
from backend.services.preparation_operations_service import (
    create_persisted_schedule,
)
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    persisted_payload,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL plan cancellation races must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _plan_payload() -> dict:
    recipe = {
        "id": "fixture-recipe",
        "name": "Reviewed preparation meal",
        "description": "PostgreSQL repair cancellation fixture",
        "ingredients": ["1 cup rice"],
        "ingredient_lines": [],
        "servings": 2,
        "calories": 400,
        "macros": {"protein_g": 10, "carbs_g": 70, "fat_g": 5},
        "flavor_profile": {},
        "tags": [],
        "instructions": ["Prepare", "Cook"],
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


def _create_linked_proposal(db):
    plan = DBMealPlan(
        user_id=OWNER_ID,
        household_id=HOUSEHOLD_ID,
        schema_version="2",
        plan_data=_plan_payload(),
        status="approved",
        version=1,
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

    calendar = create_calendar(
        db,
        version="plan-cancellation-race-v1",
        key="plan-cancellation-calendar-v1",
    )
    schedule_payload = persisted_payload(
        calendar,
        key="plan-cancellation-source-schedule-v1",
    ).model_copy(
        update={
            "source_plan_id": plan.id,
            "source_plan_version": plan.version,
        }
    )
    source = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=schedule_payload,
    )
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(
            schedule=source,
            calendar=calendar,
            key="plan-cancellation-repair-proposal-v1",
        ),
    )
    return plan, source, proposal


def _accept_worker(factory, barrier: Barrier, proposal):
    session = factory()
    try:
        barrier.wait(timeout=20)
        accepted = accept_repair_proposal_with_source_guard(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(
                proposal,
                key="pg-plan-cancellation-acceptance",
            ),
        )
        return {
            "kind": "accepted",
            "acceptance_id": accepted.acceptance.id,
            "schedule_id": accepted.acceptance.created_schedule_id,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "acceptance_conflict",
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def _cancel_worker(factory, barrier: Barrier, plan):
    session = factory()
    try:
        barrier.wait(timeout=20)
        cancelled = transition_household_plan(
            session,
            household_id=HOUSEHOLD_ID,
            plan_id=plan.id,
            actor_user_id=OWNER_ID,
            event_type=HouseholdPlanEventType.CANCELLED,
            payload=HouseholdPlanTransitionRequest.model_validate(
                {
                    "expected_version": plan.version,
                    "reason": (
                        "Cancel the source plan during repair acceptance review"
                    ),
                    "idempotency_key": "pg-plan-cancellation-transition",
                    "metadata": {"race_probe": True},
                }
            ),
        )
        return {
            "kind": "cancelled",
            "plan_version": cancelled.version,
            "plan_status": cancelled.status.value,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "cancellation_conflict",
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def test_postgres_source_plan_cancellation_dominates_repair_acceptance(db):
    factory = _session_factory(db)
    plan, source, proposal = _create_linked_proposal(db)
    initial_schedule_count = db.query(DBPersistedPreparationSchedule).count()
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        acceptance_future = pool.submit(
            _accept_worker,
            factory,
            barrier,
            proposal,
        )
        cancellation_future = pool.submit(
            _cancel_worker,
            factory,
            barrier,
            plan,
        )
        results = [
            acceptance_future.result(timeout=40),
            cancellation_future.result(timeout=40),
        ]

    cancellation = next(value for value in results if value["kind"] == "cancelled")
    assert cancellation["plan_status"] == "cancelled"
    assert cancellation["plan_version"] == plan.version + 1
    assert sum(value["kind"] == "cancelled" for value in results) == 1
    assert sum(
        value["kind"] in {"accepted", "acceptance_conflict"}
        for value in results
    ) == 1

    db.expire_all()
    final_plan = db.get(DBMealPlan, plan.id)
    assert final_plan is not None
    assert final_plan.status == "cancelled"
    assert final_plan.version == plan.version + 1
    assert final_plan.cancelled_at is not None
    assert final_plan.cancellation_reason

    final_source = db.get(DBPersistedPreparationSchedule, source.id)
    assert final_source is not None
    assert final_source.status == "invalidated"
    assert final_source.source_plan_id == plan.id
    assert final_source.source_plan_version == plan.version

    acceptance_rows = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .all()
    )
    replacements = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id
            == proposal.id
        )
        .all()
    )
    final_proposal = db.get(DBPreparationRepairProposal, proposal.id)
    assert final_proposal is not None

    acceptance_result = next(
        value
        for value in results
        if value["kind"] in {"accepted", "acceptance_conflict"}
    )
    if acceptance_result["kind"] == "accepted":
        assert final_proposal.status == "accepted"
        assert len(acceptance_rows) == 1
        assert len(replacements) == 1
        replacement = replacements[0]
        assert replacement.id == acceptance_result["schedule_id"]
        assert replacement.status == "invalidated"
        assert replacement.source_plan_id == plan.id
        assert replacement.source_plan_version == plan.version
        assert db.query(DBPersistedPreparationSchedule).count() == (
            initial_schedule_count + 1
        )
        invalidated_schedule_ids = {
            value.schedule_id
            for value in (
                db.query(DBPreparationScheduleEvent)
                .filter(
                    DBPreparationScheduleEvent.event_type == "invalidated",
                    DBPreparationScheduleEvent.schedule_id.in_(
                        [source.id, replacement.id]
                    ),
                )
                .all()
            )
        }
        assert invalidated_schedule_ids == {source.id, replacement.id}
    else:
        assert acceptance_result["status"] == 409
        assert acceptance_result["code"] in {
            "repair_acceptance_identity_mismatch",
            "repair_acceptance_source_status_changed",
            "source_plan_not_approved",
            "source_plan_version_mismatch",
        }
        assert final_proposal.status == "proposed"
        assert acceptance_rows == []
        assert replacements == []
        assert db.query(DBPersistedPreparationSchedule).count() == (
            initial_schedule_count
        )

    plan_events = (
        db.query(DBHouseholdPlanEvent)
        .filter(DBHouseholdPlanEvent.plan_id == plan.id)
        .all()
    )
    assert len(plan_events) == 1
    assert plan_events[0].event_type == "cancelled"
    assert plan_events[0].event_metadata[
        "invalidated_preparation_schedule_count"
    ] in {1, 2}

    proposal_event_types = [
        value.event_type
        for value in (
            db.query(DBPreparationRepairProposalEvent)
            .filter(DBPreparationRepairProposalEvent.proposal_id == proposal.id)
            .order_by(DBPreparationRepairProposalEvent.id)
            .all()
        )
    ]
    assert proposal_event_types in [
        ["created"],
        ["created", "accepted"],
    ]

    live_linked_schedule_count = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_plan_id == plan.id,
            DBPersistedPreparationSchedule.status.in_(["draft", "approved"]),
        )
        .count()
    )
    assert live_linked_schedule_count == 0
