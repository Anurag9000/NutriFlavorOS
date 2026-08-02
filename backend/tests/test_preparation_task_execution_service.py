from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBUser
from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    PreparationScheduleStatus,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionState,
)
from backend.services.preparation_operations_service import (
    create_persisted_schedule,
    register_resource_calendar,
    transition_schedule,
)
from backend.services.preparation_task_completion_service import (
    complete_schedule_with_execution_guard,
)
from backend.services.preparation_task_execution_service import (
    get_task_execution_overview,
    record_task_execution_event,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    calendar_payload,
    persisted_payload,
    transition_payload,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    owner = DBUser(
        id=OWNER_ID,
        name="Owner",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    household = DBHousehold(
        id=HOUSEHOLD_ID,
        owner_user_id=owner.id,
        name="Preparation home",
        timezone="UTC",
        version=1,
    )
    session.add_all([owner, household])
    session.commit()
    try:
        yield session
    finally:
        session.close()


def create_approved_schedule(db):
    calendar = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload("execution-v1", "execution-calendar-v1"),
    )
    draft = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=persisted_payload(calendar, "execution-schedule-v1"),
    )
    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            draft.version,
            "execution-approve-v1",
            "Approved for explicit household execution",
        ),
    )
    assert approved.status == PreparationScheduleStatus.APPROVED
    return approved


def event_payload(
    version: int,
    actual_minute: int,
    key: str,
    *,
    reason: str | None = None,
):
    return PreparationTaskExecutionEventCreate.model_validate(
        {
            "expected_schedule_version": version,
            "actual_minute": actual_minute,
            "reason": reason,
            "notes": "User-confirmed fixture event",
            "idempotency_key": key,
            "metadata": {"source": "test"},
        }
    )


def test_execution_requires_approved_schedule_and_known_task(db):
    calendar = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload("draft-execution", "draft-execution-calendar"),
    )
    draft = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=persisted_payload(calendar, "draft-execution-schedule"),
    )
    planned = draft.schedule.scheduled[0]
    with pytest.raises(HTTPException) as exc:
        record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=draft.id,
            task_id=planned.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=event_payload(
                draft.version,
                planned.start_minute,
                "draft-task-start",
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "approved_schedule_required"

    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            draft.version,
            "draft-execution-approve",
            "Approve fixture schedule",
        ),
    )
    with pytest.raises(HTTPException) as exc:
        record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id="unknown.task",
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=event_payload(
                approved.version,
                0,
                "unknown-task-start",
            ),
        )
    assert exc.value.status_code == 404


def test_start_and_complete_increment_schedule_version_and_are_idempotent(db):
    approved = create_approved_schedule(db)
    overview = get_task_execution_overview(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    task = overview.tasks[0].task
    started = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            task.start_minute,
            "task-start-idempotent",
        ),
    )
    assert started.task.state == PreparationTaskExecutionState.IN_PROGRESS
    assert started.event.deviation_minutes == 0
    assert started.schedule.version == approved.version + 1
    assert started.event.schedule_version_before == approved.version
    assert started.event.schedule_version_after == started.schedule.version

    retry = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            task.start_minute,
            "task-start-idempotent",
        ),
    )
    assert retry.event.id == started.event.id
    assert retry.schedule.version == started.schedule.version

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
            "task-complete-idempotent",
        ),
    )
    assert completed.task.state == PreparationTaskExecutionState.COMPLETED
    assert completed.schedule.version == started.schedule.version + 1


def test_invalid_transitions_and_idempotency_conflicts_fail_closed(db):
    approved = create_approved_schedule(db)
    task = get_task_execution_overview(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    ).tasks[0].task
    with pytest.raises(HTTPException) as exc:
        record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.COMPLETED,
            payload=event_payload(
                approved.version,
                task.finish_minute,
                "complete-before-start",
            ),
        )
    assert exc.value.detail["code"] == "invalid_task_execution_transition"

    started = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            task.start_minute,
            "reused-task-key",
        ),
    )
    with pytest.raises(HTTPException) as exc:
        record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=event_payload(
                approved.version,
                task.start_minute + 1,
                "reused-task-key",
                reason="Started one minute late",
            ),
        )
    assert exc.value.detail["code"] == "task_event_idempotency_conflict"
    assert started.task.state == PreparationTaskExecutionState.IN_PROGRESS


def test_skip_and_timing_deviations_require_reasons(db):
    approved = create_approved_schedule(db)
    overview = get_task_execution_overview(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    first = overview.tasks[0].task
    second = overview.tasks[1].task

    with pytest.raises(HTTPException) as exc:
        record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=first.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=event_payload(
                approved.version,
                first.start_minute + 5,
                "late-start-without-reason",
            ),
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "task_execution_reason_required"

    started = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=first.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            first.start_minute + 5,
            "late-start-with-reason",
            reason="Household started five minutes late",
        ),
    )
    assert started.event.deviation_minutes == 5

    with pytest.raises(HTTPException) as exc:
        record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=second.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.SKIPPED,
            payload=event_payload(
                started.schedule.version,
                second.start_minute,
                "skip-without-reason",
            ),
        )
    assert exc.value.detail["code"] == "task_execution_reason_required"

    skipped = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=second.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.SKIPPED,
        payload=event_payload(
            started.schedule.version,
            second.start_minute,
            "skip-with-reason",
            reason="Household explicitly skipped this task",
        ),
    )
    assert skipped.task.state == PreparationTaskExecutionState.SKIPPED
    assert skipped.event.deviation_minutes == 0


def test_schedule_completion_requires_every_task_terminal(db):
    approved = create_approved_schedule(db)
    overview = get_task_execution_overview(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    with pytest.raises(HTTPException) as exc:
        complete_schedule_with_execution_guard(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            actor_user_id=OWNER_ID,
            payload=transition_payload(
                approved.version,
                "complete-before-tasks",
                "Attempted completion before task evidence",
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "schedule_tasks_not_terminal"

    current_version = approved.version
    for index, task_view in enumerate(overview.tasks):
        task = task_view.task
        started = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=event_payload(
                current_version,
                task.start_minute,
                f"terminal-start-{index}",
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
                f"terminal-complete-{index}",
            ),
        )
        current_version = completed.schedule.version

    completed_schedule = complete_schedule_with_execution_guard(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        actor_user_id=OWNER_ID,
        payload=transition_payload(
            current_version,
            "complete-after-tasks",
            "All deterministic tasks explicitly completed",
        ),
    )
    assert completed_schedule.status == PreparationScheduleStatus.COMPLETED
    final = get_task_execution_overview(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    assert final.remaining_count == 0
    assert final.completed_count == len(final.tasks)
