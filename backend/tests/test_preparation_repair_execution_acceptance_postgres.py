from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBResourceCalendarVersion,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.services.preparation_task_execution_replacement_guard_service import (
    record_task_execution_event_with_replacement_guard,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    db,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload
from backend.tests.test_preparation_task_execution_service import (
    create_approved_schedule,
    event_payload,
)


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL acceptance/execution races must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _accept_worker(factory, barrier: Barrier, proposal):
    session = factory()
    try:
        barrier.wait(timeout=20)
        result = accept_repair_proposal_with_source_guard(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(
                proposal,
                key="pg-repair-accept-versus-source-start",
            ),
        )
        return {
            "kind": "accepted",
            "acceptance_id": result.acceptance.id,
            "schedule_id": result.acceptance.created_schedule_id,
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


def _start_worker(factory, barrier: Barrier, source, task):
    session = factory()
    try:
        barrier.wait(timeout=20)
        result = record_task_execution_event_with_replacement_guard(
            session,
            household_id=HOUSEHOLD_ID,
            schedule_id=source.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=event_payload(
                source.version,
                task.start_minute,
                "pg-source-start-versus-repair-accept",
            ),
        )
        return {
            "kind": "started",
            "event_id": result.event.id,
            "schedule_version": result.schedule.version,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "execution_conflict",
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def test_postgres_acceptance_racing_source_start_has_one_authoritative_outcome(db):
    factory = _session_factory(db)
    source = create_approved_schedule(db)
    calendar = db.get(DBResourceCalendarVersion, source.calendar_version_id)
    assert calendar is not None
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(
            schedule=source,
            calendar=calendar,
            key="pg-repair-proposal-versus-source-start",
        ),
    )
    task = source.schedule.scheduled[0]
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        accept_future = pool.submit(
            _accept_worker,
            factory,
            barrier,
            proposal,
        )
        start_future = pool.submit(
            _start_worker,
            factory,
            barrier,
            source,
            task,
        )
        results = [
            accept_future.result(timeout=40),
            start_future.result(timeout=40),
        ]

    db.expire_all()
    acceptance_count = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .count()
    )
    replacement_count = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id == proposal.id
        )
        .count()
    )
    source_event_count = (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(DBPreparationTaskExecutionEvent.schedule_id == source.id)
        .count()
    )

    assert sum(value["kind"] in {"accepted", "started"} for value in results) == 1
    assert sum("conflict" in value["kind"] for value in results) == 1
    if acceptance_count == 1:
        assert replacement_count == 1
        assert source_event_count == 0
        conflict = next(value for value in results if "conflict" in value["kind"])
        assert conflict["status"] == 409
        assert conflict["code"] == "source_schedule_has_accepted_replacement"
    else:
        assert acceptance_count == 0
        assert replacement_count == 0
        assert source_event_count == 1
        conflict = next(value for value in results if "conflict" in value["kind"])
        assert conflict["status"] == 409
        assert conflict["code"] in {
            "repair_acceptance_identity_mismatch",
            "repair_acceptance_source_has_execution_history",
            "repair_source_version_mismatch",
        }
