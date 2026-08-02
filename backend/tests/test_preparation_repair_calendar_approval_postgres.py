from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_operations_service import (
    register_resource_calendar,
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
    calendar_payload,
    transition_payload,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL repair approval races must never run on SQLite"
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


def _supersede_worker(factory, barrier: Barrier):
    session = factory()
    try:
        barrier.wait(timeout=20)
        successor = register_resource_calendar(
            session,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=calendar_payload(
                "calendar-approval-race-v2",
                "pg-calendar-approval-race-v2",
                second_window_start=65,
            ),
        )
        return {
            "kind": "superseded",
            "calendar_id": successor.id,
            "calendar_hash": successor.content_hash,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "supersession_conflict",
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def test_postgres_calendar_supersession_dominates_repaired_owner_approval(db):
    factory = _session_factory(db)
    calendar, source, proposal = create_proposal(db)
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="pg-calendar-approval-race-acceptance",
        ),
    )
    draft_id = accepted.acceptance.created_schedule_id
    draft = db.get(DBPersistedPreparationSchedule, draft_id)
    assert draft is not None
    assert draft.status == "draft"
    draft_version = draft.version
    approval_payload = transition_payload(
        draft_version,
        "pg-calendar-approval-race-approval",
        "Approve the repaired draft during calendar supersession",
    )
    old_calendar_id = calendar.id
    source_id = source.id
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        approval_future = pool.submit(
            _approve_worker,
            factory,
            barrier,
            draft_id,
            approval_payload,
        )
        supersession_future = pool.submit(
            _supersede_worker,
            factory,
            barrier,
        )
        results = [
            approval_future.result(timeout=40),
            supersession_future.result(timeout=40),
        ]

    supersession = next(value for value in results if value["kind"] == "superseded")
    assert sum(value["kind"] == "superseded" for value in results) == 1
    assert sum(
        value["kind"] in {"approved", "approval_conflict"}
        for value in results
    ) == 1

    db.expire_all()
    old_calendar = db.get(DBResourceCalendarVersion, old_calendar_id)
    successor = db.get(DBResourceCalendarVersion, supersession["calendar_id"])
    final_source = db.get(DBPersistedPreparationSchedule, source_id)
    final_draft = db.get(DBPersistedPreparationSchedule, draft_id)
    assert old_calendar is not None
    assert successor is not None
    assert final_source is not None
    assert final_draft is not None
    assert old_calendar.active is False
    assert successor.active is True
    assert successor.content_hash == supersession["calendar_hash"]
    assert final_source.status == "invalidated"
    assert final_draft.status == "invalidated"
    assert final_draft.calendar_version_id == old_calendar_id

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
            "schedule_calendar_stale",
            "repair_schedule_source_stale",
        }
        assert final_draft.version == draft_version + 1
        assert draft_event_types == ["created", "invalidated"]

    live_old_calendar_schedule_count = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.calendar_version_id == old_calendar_id,
            DBPersistedPreparationSchedule.status.in_(["draft", "approved"]),
        )
        .count()
    )
    assert live_old_calendar_schedule_count == 0
