#!/usr/bin/env python3
"""PostgreSQL race probe for user-confirmed preparation task execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Callable

from backend.database import SessionLocal
from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_operations_service import transition_schedule
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from scripts.check_preparation_operations_concurrency import (
    HOUSEHOLD_ID,
    USER_ID,
    _calendar,
    _create_schedule,
    _register,
    _reset,
    _schedule_payload,
    _seed,
)


def _run_pair(left: Callable[[], object], right: Callable[[], object]):
    barrier = Barrier(2)

    def execute(label: str, callback: Callable[[], object]):
        barrier.wait(timeout=10)
        try:
            return label, callback()
        except Exception as exc:  # Deliberately captured for race assertions.
            return label, exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(execute, "left", left),
            pool.submit(execute, "right", right),
        ]
        return [future.result(timeout=45) for future in futures]


def _approved_schedule(key: str):
    calendar = _register(_calendar(f"{key}-calendar", f"{key}-calendar-key"))
    draft = _create_schedule(_schedule_payload(calendar, f"{key}-schedule-key"))
    with SessionLocal() as db:
        return transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=draft.id,
            actor_user_id=USER_ID,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=ScheduleStateTransitionRequest.model_validate(
                {
                    "expected_version": draft.version,
                    "reason": "CI approved task-execution race fixture",
                    "idempotency_key": f"{key}-approve",
                    "metadata": {"probe": "postgresql"},
                }
            ),
        )


def _record(
    *,
    schedule_id: int,
    task_id: str,
    event_type: PreparationTaskExecutionEventType,
    key: str,
    expected_version: int,
    actual_minute: int,
    reason: str | None = None,
):
    with SessionLocal() as db:
        return record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule_id,
            task_id=task_id,
            actor_user_id=USER_ID,
            event_type=event_type,
            payload=PreparationTaskExecutionEventCreate.model_validate(
                {
                    "expected_schedule_version": expected_version,
                    "actual_minute": actual_minute,
                    "reason": reason,
                    "notes": "CI PostgreSQL task execution probe",
                    "idempotency_key": key,
                    "metadata": {"probe": "postgresql"},
                }
            ),
        )


def _assert_identical_start_collapses() -> None:
    schedule = _approved_schedule("identical-task-start")
    task = schedule.schedule.scheduled[0]
    callback = lambda: _record(
        schedule_id=schedule.id,
        task_id=task.task_id,
        event_type=PreparationTaskExecutionEventType.STARTED,
        key="identical-task-start-event",
        expected_version=schedule.version,
        actual_minute=task.start_minute,
    )
    results = _run_pair(callback, callback)
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    assert len({value.event.id for _, value in results}) == 1
    with SessionLocal() as db:
        row = db.get(DBPersistedPreparationSchedule, schedule.id)
        events = db.query(DBPreparationTaskExecutionEvent).filter(
            DBPreparationTaskExecutionEvent.schedule_id == schedule.id
        ).all()
        assert row.version == schedule.version + 1
        assert len(events) == 1
        assert events[0].event_type == PreparationTaskExecutionEventType.STARTED.value


def _assert_competing_start_skip_has_one_winner() -> None:
    schedule = _approved_schedule("competing-task-event")
    task = schedule.schedule.scheduled[0]
    results = _run_pair(
        lambda: _record(
            schedule_id=schedule.id,
            task_id=task.task_id,
            event_type=PreparationTaskExecutionEventType.STARTED,
            key="competing-task-start",
            expected_version=schedule.version,
            actual_minute=task.start_minute,
        ),
        lambda: _record(
            schedule_id=schedule.id,
            task_id=task.task_id,
            event_type=PreparationTaskExecutionEventType.SKIPPED,
            key="competing-task-skip",
            expected_version=schedule.version,
            actual_minute=task.start_minute,
            reason="CI deliberately skipped competing task",
        ),
    )
    successes = [value for _, value in results if not isinstance(value, Exception)]
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert len(successes) == 1, results
    assert len(errors) == 1, results
    with SessionLocal() as db:
        row = db.get(DBPersistedPreparationSchedule, schedule.id)
        events = db.query(DBPreparationTaskExecutionEvent).filter(
            DBPreparationTaskExecutionEvent.schedule_id == schedule.id
        ).all()
        assert row.version == schedule.version + 1
        assert len(events) == 1
        assert events[0].event_type in {
            PreparationTaskExecutionEventType.STARTED.value,
            PreparationTaskExecutionEventType.SKIPPED.value,
        }


def main() -> int:
    _reset()
    _seed()
    try:
        _assert_identical_start_collapses()
        _reset()
        _seed()
        _assert_competing_start_skip_has_one_winner()
        print("Preparation task execution PostgreSQL concurrency probe passed")
        return 0
    finally:
        _reset()


if __name__ == "__main__":
    raise SystemExit(main())
