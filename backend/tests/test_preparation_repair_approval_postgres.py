from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from backend.domain.preparation_operations import ScheduleStateTransitionRequest
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.services.preparation_repair_approval_guard_service import (
    approve_schedule_with_repair_acceptance_guard,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    db,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL repaired-draft approval races must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _approved_draft(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="pg-repair-approval-race-acceptance",
        ),
    )
    return accepted.acceptance.created_schedule_id


def _approve_worker(
    factory,
    barrier: Barrier,
    schedule_id: int,
    *,
    key: str,
):
    session = factory()
    try:
        barrier.wait(timeout=20)
        value = approve_schedule_with_repair_acceptance_guard(
            session,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule_id,
            actor_user_id=OWNER_ID,
            payload=ScheduleStateTransitionRequest.model_validate(
                {
                    "expected_version": 1,
                    "reason": "Approve the accepted repaired draft",
                    "idempotency_key": key,
                }
            ),
        )
        return {
            "kind": "approved",
            "schedule_id": value.id,
            "version": value.version,
            "status": value.status.value,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "conflict",
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def _assert_one_approval(db, schedule_id: int):
    db.expire_all()
    schedule = db.get(DBPersistedPreparationSchedule, schedule_id)
    events = (
        db.query(DBPreparationScheduleEvent)
        .filter(
            DBPreparationScheduleEvent.schedule_id == schedule_id,
            DBPreparationScheduleEvent.event_type == "approved",
        )
        .all()
    )
    assert schedule.status == "approved"
    assert schedule.version == 2
    assert len(events) == 1
    assert events[0].from_status == "draft"
    assert events[0].to_status == "approved"
    return schedule, events[0]


def test_postgres_exact_duplicate_repaired_approval_returns_one_transition(db):
    factory = _session_factory(db)
    schedule_id = _approved_draft(db)
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: _approve_worker(
                    factory,
                    barrier,
                    schedule_id,
                    key="pg-repair-approval-exact-duplicate",
                ),
                range(2),
            )
        )

    schedule, _ = _assert_one_approval(db, schedule_id)
    approved = [value for value in results if value["kind"] == "approved"]
    assert len(approved) == 2
    assert {value["schedule_id"] for value in approved} == {schedule.id}
    assert {value["version"] for value in approved} == {2}
    assert {value["status"] for value in approved} == {"approved"}


def test_postgres_competing_repaired_approval_keys_create_one_transition(db):
    factory = _session_factory(db)
    schedule_id = _approved_draft(db)
    barrier = Barrier(2)
    keys = ["pg-repair-approval-competing-a", "pg-repair-approval-competing-b"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _approve_worker,
                factory,
                barrier,
                schedule_id,
                key=key,
            )
            for key in keys
        ]
        results = [future.result(timeout=40) for future in futures]

    _assert_one_approval(db, schedule_id)
    assert sum(value["kind"] == "approved" for value in results) == 1
    conflicts = [value for value in results if value["kind"] == "conflict"]
    assert len(conflicts) == 1
    assert conflicts[0]["status"] == 409
    assert conflicts[0]["code"] in {
        "schedule_version_mismatch",
        "schedule_transition_not_allowed",
        "schedule_event_idempotency_conflict",
    }
