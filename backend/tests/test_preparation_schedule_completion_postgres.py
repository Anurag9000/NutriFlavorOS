from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    PreparationScheduleStatus,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)
from backend.services.preparation_operations_service import transition_schedule
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    transition_payload,
)


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL completion authority races must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _event_payload(
    *,
    version: int,
    minute: int,
    key: str,
) -> PreparationTaskExecutionEventCreate:
    return PreparationTaskExecutionEventCreate.model_validate(
        {
            "expected_schedule_version": version,
            "actual_minute": minute,
            "reason": None,
            "notes": "PostgreSQL completion authority race",
            "idempotency_key": key,
            "metadata": {"race_probe": True},
        }
    )


def _final_task_worker(factory, barrier: Barrier, schedule_id: int, task, version: int):
    session = factory()
    try:
        barrier.wait(timeout=20)
        result = record_task_execution_event(
            session,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule_id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.COMPLETED,
            payload=_event_payload(
                version=version,
                minute=task.finish_minute,
                key="pg-final-task-completion",
            ),
        )
        return {
            "kind": "task_completed",
            "schedule_version": result.schedule.version,
            "event_id": result.event.id,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "conflict",
            "status": exc.status_code,
            "code": exc.detail.get("code") if isinstance(exc.detail, dict) else str(exc.detail),
        }
    finally:
        session.close()


def _schedule_completion_worker(factory, barrier: Barrier, schedule_id: int, version: int):
    session = factory()
    try:
        barrier.wait(timeout=20)
        result = transition_schedule(
            session,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.COMPLETED,
            payload=transition_payload(
                version,
                "pg-schedule-completion-race",
                "Race schedule completion against the final task event",
            ),
        )
        return {
            "kind": "schedule_completed",
            "schedule_version": result.version,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "conflict",
            "status": exc.status_code,
            "code": exc.detail.get("code") if isinstance(exc.detail, dict) else str(exc.detail),
        }
    finally:
        session.close()


def test_postgres_schedule_cannot_complete_ahead_of_final_task_event(db):
    factory = _session_factory(db)
    calendar = create_calendar(
        db,
        version="completion-race-v1",
        key="completion-race-calendar-v1",
    )
    draft = create_schedule(db, calendar, key="completion-race-schedule-v1")
    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            draft.version,
            "completion-race-approve-v1",
            "Approve schedule for completion authority race",
        ),
    )
    tasks = sorted(
        approved.schedule.scheduled,
        key=lambda value: (
            value.start_minute,
            value.finish_minute,
            value.task_id,
        ),
    )
    assert len(tasks) >= 2

    current_version = approved.version
    for index, task in enumerate(tasks[:-1]):
        started = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=_event_payload(
                version=current_version,
                minute=task.start_minute,
                key=f"pg-prior-task-start-{index}",
            ),
        )
        completed = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.COMPLETED,
            payload=_event_payload(
                version=started.schedule.version,
                minute=task.finish_minute,
                key=f"pg-prior-task-complete-{index}",
            ),
        )
        current_version = completed.schedule.version

    final_task = tasks[-1]
    started_final = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=final_task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=_event_payload(
            version=current_version,
            minute=final_task.start_minute,
            key="pg-final-task-start",
        ),
    )
    race_version = started_final.schedule.version
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        task_future = pool.submit(
            _final_task_worker,
            factory,
            barrier,
            approved.id,
            final_task,
            race_version,
        )
        schedule_future = pool.submit(
            _schedule_completion_worker,
            factory,
            barrier,
            approved.id,
            race_version,
        )
        results = [
            task_future.result(timeout=40),
            schedule_future.result(timeout=40),
        ]

    assert sum(value["kind"] == "task_completed" for value in results) == 1
    assert sum(value["kind"] == "schedule_completed" for value in results) == 0
    conflicts = [value for value in results if value["kind"] == "conflict"]
    assert len(conflicts) == 1
    assert conflicts[0]["status"] == 409
    assert conflicts[0]["code"] in {
        "schedule_tasks_not_terminal",
        "schedule_version_conflict",
    }

    db.expire_all()
    row = db.get(DBPersistedPreparationSchedule, approved.id)
    assert row is not None
    assert row.status == PreparationScheduleStatus.APPROVED.value
    assert row.version == race_version + 1
    terminal_version = row.version

    task_events = (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(DBPreparationTaskExecutionEvent.schedule_id == approved.id)
        .all()
    )
    assert len(task_events) == len(tasks) * 2
    assert sum(
        value.event_type == PreparationTaskExecutionEventType.COMPLETED.value
        for value in task_events
    ) == len(tasks)
    assert (
        db.query(DBPreparationScheduleEvent)
        .filter(
            DBPreparationScheduleEvent.schedule_id == approved.id,
            DBPreparationScheduleEvent.event_type
            == PreparationScheduleEventType.COMPLETED.value,
        )
        .count()
        == 0
    )

    completed = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.COMPLETED,
        payload=transition_payload(
            terminal_version,
            "pg-schedule-completion-after-final-task",
            "Complete only after the final task event committed",
        ),
    )
    assert completed.status == PreparationScheduleStatus.COMPLETED
    assert completed.version == terminal_version + 1
    assert (
        db.query(DBPreparationScheduleEvent)
        .filter(
            DBPreparationScheduleEvent.schedule_id == approved.id,
            DBPreparationScheduleEvent.event_type
            == PreparationScheduleEventType.COMPLETED.value,
        )
        .count()
        == 1
    )
