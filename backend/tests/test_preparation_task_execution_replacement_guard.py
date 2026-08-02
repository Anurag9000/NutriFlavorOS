from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.domain.preparation_operations import ScheduleStateTransitionRequest
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
)
from backend.services.preparation_operations_service import get_persisted_schedule
from backend.services.preparation_repair_approval_guard_service import (
    approve_schedule_with_repair_acceptance_guard,
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
    create_proposal,
)
from backend.tests.test_preparation_task_execution_service import event_payload


def _accept_replacement(db, *, key: str):
    _, source, proposal = create_proposal(db)
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(proposal, key=key),
    )
    return source, proposal, accepted


def test_source_schedule_rejects_task_execution_after_repair_acceptance(db):
    source, proposal, accepted = _accept_replacement(
        db,
        key="repair-source-execution-block-acceptance",
    )
    task = source.schedule.scheduled[0]

    with pytest.raises(HTTPException) as exc:
        record_task_execution_event_with_replacement_guard(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=source.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=event_payload(
                source.version,
                task.start_minute,
                "repair-source-execution-block-start",
            ),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "source_schedule_has_accepted_replacement"
    assert exc.value.detail["source_schedule_id"] == source.id
    assert exc.value.detail["source_schedule_version_at_acceptance"] == (
        source.version
    )
    assert exc.value.detail["accepted_proposal_id"] == proposal.id
    assert exc.value.detail["acceptance_id"] == accepted.acceptance.id
    assert exc.value.detail["replacement_schedule_id"] == (
        accepted.acceptance.created_schedule_id
    )


def test_approved_replacement_schedule_can_record_task_execution(db):
    _, _, accepted = _accept_replacement(
        db,
        key="repair-replacement-execution-acceptance",
    )
    replacement_id = accepted.acceptance.created_schedule_id
    approved = approve_schedule_with_repair_acceptance_guard(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=replacement_id,
        actor_user_id=OWNER_ID,
        payload=ScheduleStateTransitionRequest.model_validate(
            {
                "expected_version": 1,
                "reason": "Approve the accepted replacement for execution",
                "idempotency_key": "repair-replacement-execution-approval",
            }
        ),
    )
    task = approved.schedule.scheduled[0]

    mutation = record_task_execution_event_with_replacement_guard(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=replacement_id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            task.start_minute,
            "repair-replacement-execution-start",
        ),
    )

    assert mutation.schedule.id == replacement_id
    assert mutation.task.task.task_id == task.task_id
    assert mutation.task.state.value == "in_progress"
    refreshed = get_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=replacement_id,
    )
    assert refreshed.version == approved.version + 1
