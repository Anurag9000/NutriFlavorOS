from __future__ import annotations

# Preserve the complete historical service regression suite and helper surface.
# This public test module overrides only the obsolete implicit-completion case.
from backend.tests.preparation_operations_service_cases import *  # noqa: F401,F403

import pytest
from fastapi import HTTPException

from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    PreparationScheduleStatus,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
)
from backend.services.preparation_operations_service import transition_schedule
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)


def _terminal_event_payload(
    *,
    version: int,
    actual_minute: int,
    key: str,
) -> PreparationTaskExecutionEventCreate:
    return PreparationTaskExecutionEventCreate.model_validate(
        {
            "expected_schedule_version": version,
            "actual_minute": actual_minute,
            "reason": None,
            "notes": "Explicit terminality authority regression",
            "idempotency_key": key,
            "metadata": {"source": "direct_transition_test"},
        }
    )


def test_transitions_are_optimistic_idempotent_and_terminal(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    approval = transition_payload(
        1,
        "approve-schedule-0001",
        "Owner reviewed the calendar and preparation sequence",
    )
    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=approval,
    )
    retry = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=approval,
    )
    assert approved.version == 2
    assert retry.version == 2

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.COMPLETED,
            payload=transition_payload(
                1,
                "complete-with-stale-version",
                "Attempt with stale version",
            ),
        )
    assert exc.value.detail["code"] == "schedule_version_conflict"

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.COMPLETED,
            payload=transition_payload(
                approved.version,
                "complete-before-terminal-tasks",
                "Direct low-level completion must fail closed",
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "schedule_tasks_not_terminal"
    assert exc.value.detail["remaining_task_ids"] == [
        "dinner.cook",
        "dinner.prep",
    ]

    current_version = approved.version
    tasks = sorted(
        approved.schedule.scheduled,
        key=lambda value: (
            value.start_minute,
            value.finish_minute,
            value.task_id,
        ),
    )
    for index, task in enumerate(tasks):
        started = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=_terminal_event_payload(
                version=current_version,
                actual_minute=task.start_minute,
                key=f"direct-terminal-start-{index}",
            ),
        )
        completed_task = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.COMPLETED,
            payload=_terminal_event_payload(
                version=started.schedule.version,
                actual_minute=task.finish_minute,
                key=f"direct-terminal-complete-{index}",
            ),
        )
        current_version = completed_task.schedule.version

    completion = transition_payload(
        current_version,
        "complete-schedule-0001",
        "Household confirmed every deterministic task completed",
    )
    completed = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.COMPLETED,
        payload=completion,
    )
    completion_retry = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.COMPLETED,
        payload=completion,
    )
    assert completed.status == PreparationScheduleStatus.COMPLETED
    assert completion_retry.id == completed.id
    assert completion_retry.version == completed.version

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.CANCELLED,
            payload=transition_payload(
                completed.version,
                "cancel-completed-schedule",
                "Terminal schedule cannot be cancelled",
            ),
        )
    assert exc.value.detail["code"] == "invalid_schedule_transition"
