from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
    DBPreparationRepairProposalAcceptance,
)
from backend.services.household_plan_lifecycle_service import (
    transition_household_plan,
)
from backend.services.preparation_repair_approval_guard_service import (
    approve_schedule_with_repair_acceptance_guard,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    transition_payload,
)
from backend.tests.test_preparation_repair_plan_cancellation_postgres import (
    _create_linked_proposal,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
)


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL source plan approval races must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _approve_worker(factory, barrier: Barrier, schedule_id: int, payload):
    session = factory()
    try:
        barrier.wait(timeout=20)
        approved = approve_schedule_with_repair_acceptance_guard(
            session,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
        return {
            "kind": "approved",
            "schedule_id": approved.id,
            "schedule_version": approved.version,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "approval_conflict",
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def _cancel_worker(
    factory,
    barrier: Barrier,
    *,
    plan_id: int,
    plan_version: int,
):
    session = factory()
    try:
        barrier.wait(timeout=20)
        cancelled = transition_household_plan(
            session,
            household_id=HOUSEHOLD_ID,
            plan_id=plan_id,
            actor_user_id=OWNER_ID,
            event_type=HouseholdPlanEventType.CANCELLED,
            payload=HouseholdPlanTransitionRequest.model_validate(
                {
                    "expected_version": plan_version,
                    "reason": (
                        "Cancel the source plan during repaired draft approval"
                    ),
                    "idempotency_key": "pg-plan-approval-cancellation",
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


def test_postgres_source_plan_cancellation_dominates_repaired_owner_approval(db):
    factory = _session_factory(db)
    plan, source, proposal = _create_linked_proposal(db)
    plan_id = plan.id
    source_plan_version = plan.version
    source_id = source.id
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="pg-plan-approval-race-acceptance",
        ),
    )
    draft_id = accepted.acceptance.created_schedule_id
    draft = db.get(DBPersistedPreparationSchedule, draft_id)
    assert draft is not None
    assert draft.status == "draft"
    draft_version = draft.version
    approval_payload = transition_payload(
        draft_version,
        "pg-plan-approval-race-approval",
        "Approve the repaired draft during source plan cancellation",
    )
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        approval_future = pool.submit(
            _approve_worker,
            factory,
            barrier,
            draft_id,
            approval_payload,
        )
        cancellation_future = pool.submit(
            _cancel_worker,
            factory,
            barrier,
            plan_id=plan_id,
            plan_version=source_plan_version,
        )
        results = [
            approval_future.result(timeout=40),
            cancellation_future.result(timeout=40),
        ]

    cancellation = next(value for value in results if value["kind"] == "cancelled")
    assert cancellation["plan_status"] == "cancelled"
    assert cancellation["plan_version"] == source_plan_version + 1
    assert sum(value["kind"] == "cancelled" for value in results) == 1
    assert sum(
        value["kind"] in {"approved", "approval_conflict"}
        for value in results
    ) == 1

    db.expire_all()
    final_plan = db.get(DBMealPlan, plan_id)
    final_source = db.get(DBPersistedPreparationSchedule, source_id)
    final_draft = db.get(DBPersistedPreparationSchedule, draft_id)
    assert final_plan is not None
    assert final_source is not None
    assert final_draft is not None
    assert final_plan.status == "cancelled"
    assert final_plan.version == source_plan_version + 1
    assert final_source.status == "invalidated"
    assert final_draft.status == "invalidated"
    assert final_draft.source_plan_id == plan_id
    assert final_draft.source_plan_version == source_plan_version

    acceptance_rows = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.created_schedule_id == draft_id
        )
        .all()
    )
    assert len(acceptance_rows) == 1

    approval_result = next(
        value
        for value in results
        if value["kind"] in {"approved", "approval_conflict"}
    )
    draft_event_types = [
        value.event_type
        for value in (
            db.query(DBPreparationScheduleEvent)
            .filter(DBPreparationScheduleEvent.schedule_id == draft_id)
            .order_by(DBPreparationScheduleEvent.id)
            .all()
        )
    ]
    if approval_result["kind"] == "approved":
        assert approval_result["schedule_version"] == draft_version + 1
        assert final_draft.version == draft_version + 2
        assert draft_event_types == ["created", "approved", "invalidated"]
    else:
        assert approval_result["status"] == 409
        assert approval_result["code"] in {
            "schedule_version_conflict",
            "invalid_schedule_transition",
            "repair_schedule_source_stale",
            "source_plan_not_approved",
            "source_plan_version_mismatch",
        }
        assert final_draft.version == draft_version + 1
        assert draft_event_types == ["created", "invalidated"]

    plan_events = (
        db.query(DBHouseholdPlanEvent)
        .filter(DBHouseholdPlanEvent.plan_id == plan_id)
        .all()
    )
    assert len(plan_events) == 1
    assert plan_events[0].event_type == "cancelled"
    assert plan_events[0].event_metadata[
        "invalidated_preparation_schedule_count"
    ] == 2

    live_linked_schedule_count = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_plan_id == plan_id,
            DBPersistedPreparationSchedule.status.in_(["draft", "approved"]),
        )
        .count()
    )
    assert live_linked_schedule_count == 0
