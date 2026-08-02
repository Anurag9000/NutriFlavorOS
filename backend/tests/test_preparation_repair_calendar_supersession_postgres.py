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
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_operations_service import (
    register_resource_calendar,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    calendar_payload,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL calendar supersession races must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _accept_worker(factory, barrier: Barrier, proposal_id: int, payload):
    session = factory()
    try:
        barrier.wait(timeout=20)
        accepted = accept_repair_proposal_with_source_guard(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
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


def _supersede_worker(factory, barrier: Barrier):
    session = factory()
    try:
        barrier.wait(timeout=20)
        successor = register_resource_calendar(
            session,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=calendar_payload(
                "calendar-supersession-v2",
                "pg-calendar-supersession-v2",
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


def test_postgres_calendar_supersession_dominates_repair_acceptance(db):
    factory = _session_factory(db)
    calendar, source, proposal = create_proposal(db)
    calendar_id = calendar.id
    source_id = source.id
    proposal_id = proposal.id
    accept_payload = acceptance_payload(
        proposal,
        key="pg-calendar-supersession-acceptance",
    )
    initial_schedule_count = db.query(DBPersistedPreparationSchedule).count()
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        acceptance_future = pool.submit(
            _accept_worker,
            factory,
            barrier,
            proposal_id,
            accept_payload,
        )
        supersession_future = pool.submit(
            _supersede_worker,
            factory,
            barrier,
        )
        results = [
            acceptance_future.result(timeout=40),
            supersession_future.result(timeout=40),
        ]

    supersession = next(value for value in results if value["kind"] == "superseded")
    assert sum(value["kind"] == "superseded" for value in results) == 1
    assert sum(
        value["kind"] in {"accepted", "acceptance_conflict"}
        for value in results
    ) == 1

    db.expire_all()
    old_calendar = db.get(DBResourceCalendarVersion, calendar_id)
    successor = db.get(DBResourceCalendarVersion, supersession["calendar_id"])
    assert old_calendar is not None
    assert successor is not None
    assert old_calendar.active is False
    assert successor.active is True
    assert successor.content_hash == supersession["calendar_hash"]

    final_source = db.get(DBPersistedPreparationSchedule, source_id)
    assert final_source is not None
    assert final_source.status == "invalidated"
    assert final_source.calendar_version_id == calendar_id

    acceptance_rows = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
        .all()
    )
    replacements = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id
            == proposal_id
        )
        .all()
    )
    final_proposal = db.get(DBPreparationRepairProposal, proposal_id)
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
        assert replacement.calendar_version_id == calendar_id
        assert replacement.status == "invalidated"
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
                        [source_id, replacement.id]
                    ),
                )
                .all()
            )
        }
        assert invalidated_schedule_ids == {source_id, replacement.id}
    else:
        assert acceptance_result["status"] == 409
        assert acceptance_result["code"] in {
            "repair_acceptance_identity_mismatch",
            "repair_acceptance_source_status_changed",
            "repair_acceptance_calendar_stale",
        }
        assert final_proposal.status == "proposed"
        assert acceptance_rows == []
        assert replacements == []
        assert db.query(DBPersistedPreparationSchedule).count() == (
            initial_schedule_count
        )

    proposal_event_types = [
        value.event_type
        for value in (
            db.query(DBPreparationRepairProposalEvent)
            .filter(DBPreparationRepairProposalEvent.proposal_id == proposal_id)
            .order_by(DBPreparationRepairProposalEvent.id)
            .all()
        )
    ]
    assert proposal_event_types in [
        ["created"],
        ["created", "accepted"],
    ]

    live_old_calendar_schedule_count = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.calendar_version_id == calendar_id,
            DBPersistedPreparationSchedule.status.in_(["draft", "approved"]),
        )
        .count()
    )
    assert live_old_calendar_schedule_count == 0
