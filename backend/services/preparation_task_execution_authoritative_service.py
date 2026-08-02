"""Authoritative product-facing validation for preparation task execution.

The original execution service remains the mutation implementation. This layer
validates the complete persisted deterministic schedule and append-only event
history before product reads or writes, so malformed legacy/internal rows fail
with controlled conflicts rather than leaking KeyError or inflated state.
"""

from __future__ import annotations

from typing import Dict, List

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.domain.preparation import PreparationScheduleResponse, ScheduledPreparationTask
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionMutationView,
    PreparationTaskExecutionOverview,
    PreparationTaskExecutionState,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_task_execution_service import (
    get_task_execution_overview as _get_task_execution_overview,
    record_task_execution_event as _record_task_execution_event,
)


def _conflict(code: str, message: str, **details) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": message, **details},
    )


def _schedule_row(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> DBPersistedPreparationSchedule:
    row = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return row


def _event_rows(
    db: Session,
    *,
    schedule_id: int,
) -> List[DBPreparationTaskExecutionEvent]:
    return (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(DBPreparationTaskExecutionEvent.schedule_id == schedule_id)
        .order_by(
            DBPreparationTaskExecutionEvent.created_at,
            DBPreparationTaskExecutionEvent.id,
        )
        .all()
    )


def _validated_tasks(
    schedule: DBPersistedPreparationSchedule,
) -> tuple[PreparationScheduleResponse, Dict[str, ScheduledPreparationTask]]:
    try:
        response = PreparationScheduleResponse.model_validate(schedule.schedule_payload)
    except ValidationError as exc:
        raise _conflict(
            "persisted_schedule_invalid",
            "Persisted deterministic schedule no longer validates",
        ) from exc
    if response.unscheduled:
        raise _conflict(
            "persisted_schedule_incomplete",
            "Execution requires a complete persisted schedule",
        )
    if not response.scheduled:
        raise _conflict(
            "persisted_schedule_has_no_tasks",
            "Execution requires at least one deterministic task",
        )
    tasks = {value.task_id: value for value in response.scheduled}
    if len(tasks) != len(response.scheduled):
        raise _conflict(
            "persisted_schedule_duplicate_task",
            "Persisted deterministic task IDs must be unique",
        )
    unknown_dependencies = sorted(
        {
            dependency
            for task in response.scheduled
            for dependency in task.dependencies
            if dependency not in tasks
        }
    )
    if unknown_dependencies:
        raise _conflict(
            "persisted_schedule_dependency_missing",
            "Persisted deterministic tasks reference unknown dependencies",
            unknown_dependency_ids=unknown_dependencies,
        )
    return response, tasks


def validate_task_execution_snapshot(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> tuple[
    DBPersistedPreparationSchedule,
    Dict[str, ScheduledPreparationTask],
    List[DBPreparationTaskExecutionEvent],
    Dict[str, PreparationTaskExecutionState],
]:
    """Validate deterministic tasks and the complete append-only history."""

    schedule = _schedule_row(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    response, tasks = _validated_tasks(schedule)
    events = _event_rows(db, schedule_id=schedule.id)
    states = {
        task_id: PreparationTaskExecutionState.PLANNED for task_id in tasks
    }
    previous_after: int | None = None
    horizon = response.horizon_minutes

    for event in events:
        task = tasks.get(event.task_id)
        if task is None:
            raise _conflict(
                "execution_event_task_missing",
                "Persisted execution event references a task absent from the deterministic schedule",
                event_id=event.id,
                task_id=event.task_id,
            )
        if (
            event.planned_start_minute != task.start_minute
            or event.planned_finish_minute != task.finish_minute
        ):
            raise _conflict(
                "execution_event_plan_snapshot_mismatch",
                "Persisted execution event planned timing differs from the deterministic schedule",
                event_id=event.id,
                task_id=event.task_id,
            )
        if event.actual_minute < 0 or event.actual_minute > horizon:
            raise _conflict(
                "execution_event_actual_minute_invalid",
                "Persisted execution event actual minute is outside the schedule horizon",
                event_id=event.id,
                task_id=event.task_id,
            )
        try:
            event_type = PreparationTaskExecutionEventType(event.event_type)
            from_state = PreparationTaskExecutionState(event.from_state)
            to_state = PreparationTaskExecutionState(event.to_state)
        except ValueError as exc:
            raise _conflict(
                "execution_history_invalid",
                "Persisted task execution history contains an unknown state or event",
                event_id=event.id,
                task_id=event.task_id,
            ) from exc

        expected_target = {
            PreparationTaskExecutionEventType.STARTED: (
                PreparationTaskExecutionState.IN_PROGRESS
            ),
            PreparationTaskExecutionEventType.COMPLETED: (
                PreparationTaskExecutionState.COMPLETED
            ),
            PreparationTaskExecutionEventType.SKIPPED: (
                PreparationTaskExecutionState.SKIPPED
            ),
        }[event_type]
        allowed_sources = {
            PreparationTaskExecutionEventType.STARTED: {
                PreparationTaskExecutionState.PLANNED,
            },
            PreparationTaskExecutionEventType.COMPLETED: {
                PreparationTaskExecutionState.IN_PROGRESS,
            },
            PreparationTaskExecutionEventType.SKIPPED: {
                PreparationTaskExecutionState.PLANNED,
                PreparationTaskExecutionState.IN_PROGRESS,
            },
        }[event_type]
        if (
            states[event.task_id] != from_state
            or from_state not in allowed_sources
            or to_state != expected_target
        ):
            raise _conflict(
                "execution_history_invalid",
                "Persisted task execution state transition is inconsistent",
                event_id=event.id,
                task_id=event.task_id,
            )

        if (
            event.schedule_version_after != event.schedule_version_before + 1
            or (
                previous_after is not None
                and event.schedule_version_before != previous_after
            )
        ):
            raise _conflict(
                "execution_event_version_chain_invalid",
                "Persisted task execution schedule-version chain is inconsistent",
                event_id=event.id,
                task_id=event.task_id,
            )
        previous_after = event.schedule_version_after

        expected_deviation = (
            event.actual_minute - task.start_minute
            if event_type == PreparationTaskExecutionEventType.STARTED
            else event.actual_minute - task.finish_minute
            if event_type == PreparationTaskExecutionEventType.COMPLETED
            else 0
        )
        if event.deviation_minutes != expected_deviation:
            raise _conflict(
                "execution_event_deviation_invalid",
                "Persisted task execution deviation does not match planned and actual timing",
                event_id=event.id,
                task_id=event.task_id,
            )
        if (
            event_type == PreparationTaskExecutionEventType.SKIPPED
            or expected_deviation != 0
        ) and not (event.reason and event.reason.strip()):
            raise _conflict(
                "execution_event_reason_missing",
                "Persisted skip or timing deviation lacks a nonblank reason",
                event_id=event.id,
                task_id=event.task_id,
            )
        if event_type == PreparationTaskExecutionEventType.COMPLETED:
            started = next(
                (
                    value
                    for value in events
                    if value.task_id == event.task_id
                    and value.id < event.id
                    and value.event_type
                    == PreparationTaskExecutionEventType.STARTED.value
                ),
                None,
            )
            if started is None or event.actual_minute < started.actual_minute:
                raise _conflict(
                    "execution_completion_chronology_invalid",
                    "Persisted completion lacks a valid earlier confirmed start",
                    event_id=event.id,
                    task_id=event.task_id,
                )
        if event_type == PreparationTaskExecutionEventType.STARTED:
            blocked = sorted(
                dependency
                for dependency in task.dependencies
                if states[dependency]
                not in {
                    PreparationTaskExecutionState.COMPLETED,
                    PreparationTaskExecutionState.SKIPPED,
                }
            )
            if blocked:
                raise _conflict(
                    "execution_dependency_history_invalid",
                    "Persisted task start occurred before its dependencies were terminal",
                    event_id=event.id,
                    task_id=event.task_id,
                    blocked_by=blocked,
                )
        states[event.task_id] = to_state

    if events and schedule.status == "approved" and previous_after != schedule.version:
        raise _conflict(
            "execution_event_version_chain_invalid",
            "Approved schedule version does not match its latest task execution event",
            schedule_id=schedule.id,
            current_version=schedule.version,
            latest_task_event_version=previous_after,
        )
    return schedule, tasks, events, states


def get_task_execution_overview(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> PreparationTaskExecutionOverview:
    validate_task_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    return _get_task_execution_overview(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )


def record_task_execution_event(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    task_id: str,
    actor_user_id: str,
    event_type: PreparationTaskExecutionEventType,
    payload: PreparationTaskExecutionEventCreate,
) -> PreparationTaskExecutionMutationView:
    validate_task_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    result = _record_task_execution_event(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        task_id=task_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload=payload,
    )
    validate_task_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    return result
