from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
)
from backend.preparation_operations_models import DBResourceCalendarVersion
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_proposal_read_service import (
    get_repair_proposal,
)
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload
from backend.tests.test_preparation_task_execution_service import (
    create_approved_schedule,
    db,
    event_payload,
)


def _calendar(db, schedule):
    value = db.get(DBResourceCalendarVersion, schedule.calendar_version_id)
    assert value is not None
    return value


def _start_first_task(db, schedule, *, key: str):
    task = schedule.schedule.scheduled[0]
    return record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            schedule.version,
            task.start_minute,
            key,
        ),
    )


def test_proposal_creation_rejects_source_with_task_execution_history(db):
    approved = create_approved_schedule(db)
    calendar = _calendar(db, approved)
    started = _start_first_task(
        db,
        approved,
        key="repair-boundary-start-before-proposal",
    )

    with pytest.raises(HTTPException) as exc:
        create_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=proposal_payload(
                schedule=started.schedule,
                calendar=calendar,
                key="repair-after-execution-0001",
            ),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_source_has_execution_history"


def test_existing_proposal_becomes_stale_when_execution_begins(db):
    approved = create_approved_schedule(db)
    calendar = _calendar(db, approved)
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(
            schedule=approved,
            calendar=calendar,
            key="repair-before-execution-0001",
        ),
    )
    assert proposal.current is True
    assert proposal.stale_reasons == []

    _start_first_task(
        db,
        approved,
        key="repair-boundary-start-after-proposal",
    )

    stale = get_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
    )
    assert stale.current is False
    assert "source_schedule_has_execution_history" in stale.stale_reasons
    assert "source_schedule_version_changed" in stale.stale_reasons
    assert stale.accepted is False
    assert stale.schedule_persistence_performed is False
