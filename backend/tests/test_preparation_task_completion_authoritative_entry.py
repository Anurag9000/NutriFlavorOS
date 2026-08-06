from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
)
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_task_completion_service import (
    complete_schedule_with_execution_guard,
)
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from backend.tests.test_preparation_operations_service import transition_payload
from backend.tests.test_preparation_task_execution_authoritative_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    approved_schedule,
    db,
    event_payload,
)


def test_guarded_completion_rejects_corrupted_terminal_history(db):
    approved = approved_schedule(db)
    version = approved.version
    for index, task in enumerate(approved.schedule.scheduled):
        started = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=event_payload(
                version,
                task.start_minute,
                f"completion-authoritative-start-{index}",
            ),
        )
        completed = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.COMPLETED,
            payload=event_payload(
                started.schedule.version,
                task.finish_minute,
                f"completion-authoritative-complete-{index}",
            ),
        )
        version = completed.schedule.version

    last = (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(DBPreparationTaskExecutionEvent.schedule_id == approved.id)
        .order_by(DBPreparationTaskExecutionEvent.id.desc())
        .first()
    )
    last.planned_finish_minute += 1
    # Keep the intentionally corrupted row internally valid under the database
    # deviation/reason constraints. The authoritative completion service must be
    # the layer that detects the immutable plan-snapshot mismatch.
    last.deviation_minutes = last.actual_minute - last.planned_finish_minute
    last.reason = "Deliberate structurally valid terminal snapshot corruption"
    db.add(last)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        complete_schedule_with_execution_guard(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            actor_user_id=OWNER_ID,
            payload=transition_payload(
                version,
                "completion-authoritative-final",
                "Attempt completion with corrupted task evidence",
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "execution_event_plan_snapshot_mismatch"
