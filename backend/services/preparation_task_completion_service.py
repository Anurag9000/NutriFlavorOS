"""Schedule-completion guard backed by explicit task execution evidence."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation_operations import (
    PersistedPreparationScheduleView,
    PreparationScheduleEventType,
    ScheduleStateTransitionRequest,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.services.preparation_operations_service import (
    _lock_household,
    transition_schedule,
)
from backend.services.preparation_task_execution_service import (
    assert_schedule_tasks_terminal,
)


def complete_schedule_with_execution_guard(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    payload: ScheduleStateTransitionRequest,
) -> PersistedPreparationScheduleView:
    """Complete only after every deterministic task is user-terminal.

    The household row/advisory lock remains held while the task terminality
    proof and the existing optimistic schedule transition execute. Task events
    can be written only for approved schedules and terminal tasks cannot accept
    later events, so the proof cannot be invalidated inside this transaction.
    """

    _lock_household(db, household_id)
    schedule = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if schedule.version != payload.expected_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_version_conflict",
                "message": "Schedule version changed; reload before mutating it",
                "current_version": schedule.version,
            },
        )
    assert_schedule_tasks_terminal(db, schedule=schedule)
    return transition_schedule(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        actor_user_id=actor_user_id,
        event_type=PreparationScheduleEventType.COMPLETED,
        payload=payload,
    )
