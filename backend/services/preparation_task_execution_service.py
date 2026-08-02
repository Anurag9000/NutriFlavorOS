"""Append-only, user-confirmed execution events for persisted preparation tasks."""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.preparation import PreparationScheduleResponse, ScheduledPreparationTask
from backend.domain.preparation_operations import PreparationScheduleStatus
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionEventView,
    PreparationTaskExecutionMutationView,
    PreparationTaskExecutionOverview,
    PreparationTaskExecutionState,
    PreparationTaskExecutionTaskView,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_operations_service import (
    _lock_household,
    _schedule_view,
    utcnow,
)


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fingerprint(
    *,
    schedule_id: int,
    task_id: str,
    event_type: PreparationTaskExecutionEventType,
    actor_user_id: str,
    payload: PreparationTaskExecutionEventCreate,
) -> str:
    return _canonical_hash(
        {
            "schedule_id": schedule_id,
            "task_id": task_id,
            "event_type": event_type.value,
            "actor_user_id": actor_user_id,
            "expected_schedule_version": payload.expected_schedule_version,
            "actual_minute": payload.actual_minute,
            "reason": payload.reason,
            "notes": payload.notes,
            "metadata": payload.metadata,
        }
    )


def _event_view(
    value: DBPreparationTaskExecutionEvent,
) -> PreparationTaskExecutionEventView:
    return PreparationTaskExecutionEventView(
        id=value.id,
        schedule_id=value.schedule_id,
        household_id=value.household_id,
        task_id=value.task_id,
        event_type=PreparationTaskExecutionEventType(value.event_type),
        actor_user_id=value.actor_user_id,
        from_state=PreparationTaskExecutionState(value.from_state),
        to_state=PreparationTaskExecutionState(value.to_state),
        planned_start_minute=value.planned_start_minute,
        planned_finish_minute=value.planned_finish_minute,
        actual_minute=value.actual_minute,
        deviation_minutes=value.deviation_minutes,
        reason=value.reason,
        notes=value.notes,
        metadata=dict(value.event_metadata or {}),
        idempotency_key=value.idempotency_key,
        request_fingerprint=value.request_fingerprint,
        schedule_version_before=value.schedule_version_before,
        schedule_version_after=value.schedule_version_after,
        created_at=value.created_at.isoformat(),
    )


def _scheduled_tasks(
    schedule: DBPersistedPreparationSchedule,
) -> Dict[str, ScheduledPreparationTask]:
    try:
        response = PreparationScheduleResponse.model_validate(schedule.schedule_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "persisted_schedule_invalid",
                "message": "Persisted deterministic schedule no longer validates",
            },
        ) from exc
    if response.unscheduled:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "persisted_schedule_incomplete",
                "message": "Execution requires a complete persisted schedule",
            },
        )
    tasks = {value.task_id: value for value in response.scheduled}
    if not tasks:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "persisted_schedule_has_no_tasks",
                "message": "Execution requires at least one deterministic task",
            },
        )
    if len(tasks) != len(response.scheduled):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "persisted_schedule_duplicate_task",
                "message": "Persisted deterministic task IDs must be unique",
            },
        )
    return tasks


def _events(
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


def _states(
    tasks: Dict[str, ScheduledPreparationTask],
    events: List[DBPreparationTaskExecutionEvent],
) -> Dict[str, PreparationTaskExecutionState]:
    state = {
        task_id: PreparationTaskExecutionState.PLANNED for task_id in tasks
    }
    for event in events:
        if event.task_id not in tasks:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "execution_event_task_missing",
                    "message": (
                        "Persisted execution event references a task absent from "
                        "the deterministic schedule"
                    ),
                    "task_id": event.task_id,
                },
            )
        observed = PreparationTaskExecutionState(event.from_state)
        if state[event.task_id] != observed:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "execution_history_invalid",
                    "message": "Persisted task execution history is inconsistent",
                    "task_id": event.task_id,
                },
            )
        state[event.task_id] = PreparationTaskExecutionState(event.to_state)
    return state


def _task_events(
    events: List[DBPreparationTaskExecutionEvent],
    task_id: str,
) -> List[DBPreparationTaskExecutionEvent]:
    return [value for value in events if value.task_id == task_id]


def _task_view(
    *,
    task: ScheduledPreparationTask,
    state: PreparationTaskExecutionState,
    events: List[DBPreparationTaskExecutionEvent],
) -> PreparationTaskExecutionTaskView:
    task_events = _task_events(events, task.task_id)
    started = next(
        (
            value.actual_minute
            for value in task_events
            if value.event_type == PreparationTaskExecutionEventType.STARTED.value
        ),
        None,
    )
    completed = next(
        (
            value.actual_minute
            for value in task_events
            if value.event_type == PreparationTaskExecutionEventType.COMPLETED.value
        ),
        None,
    )
    skipped = next(
        (
            value.actual_minute
            for value in task_events
            if value.event_type == PreparationTaskExecutionEventType.SKIPPED.value
        ),
        None,
    )
    terminal = next(
        (
            value
            for value in reversed(task_events)
            if value.event_type
            in {
                PreparationTaskExecutionEventType.COMPLETED.value,
                PreparationTaskExecutionEventType.SKIPPED.value,
            }
        ),
        None,
    )
    return PreparationTaskExecutionTaskView(
        task=task,
        state=state,
        latest_event_id=task_events[-1].id if task_events else None,
        started_actual_minute=started,
        completed_actual_minute=completed,
        skipped_actual_minute=skipped,
        terminal_reason=terminal.reason if terminal else None,
    )


def _overview_from_rows(
    *,
    schedule: DBPersistedPreparationSchedule,
    tasks: Dict[str, ScheduledPreparationTask],
    events: List[DBPreparationTaskExecutionEvent],
) -> PreparationTaskExecutionOverview:
    states = _states(tasks, events)
    task_views = [
        _task_view(
            task=tasks[task_id],
            state=states[task_id],
            events=events,
        )
        for task_id in sorted(
            tasks,
            key=lambda value: (
                tasks[value].start_minute,
                tasks[value].finish_minute,
                value,
            ),
        )
    ]
    counts = {
        value: sum(1 for state in states.values() if state == value)
        for value in PreparationTaskExecutionState
    }
    terminal = (
        counts[PreparationTaskExecutionState.COMPLETED]
        + counts[PreparationTaskExecutionState.SKIPPED]
    )
    return PreparationTaskExecutionOverview(
        schedule=_schedule_view(schedule),
        tasks=task_views,
        events=[_event_view(value) for value in events],
        planned_count=counts[PreparationTaskExecutionState.PLANNED],
        in_progress_count=counts[PreparationTaskExecutionState.IN_PROGRESS],
        completed_count=counts[PreparationTaskExecutionState.COMPLETED],
        skipped_count=counts[PreparationTaskExecutionState.SKIPPED],
        terminal_count=terminal,
        remaining_count=len(tasks) - terminal,
    )


def get_task_execution_overview(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> PreparationTaskExecutionOverview:
    schedule = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    tasks = _scheduled_tasks(schedule)
    events = _events(db, schedule_id=schedule.id)
    return _overview_from_rows(schedule=schedule, tasks=tasks, events=events)


def assert_schedule_tasks_terminal(
    db: Session,
    *,
    schedule: DBPersistedPreparationSchedule,
) -> None:
    tasks = _scheduled_tasks(schedule)
    events = _events(db, schedule_id=schedule.id)
    states = _states(tasks, events)
    remaining = sorted(
        task_id
        for task_id, state in states.items()
        if state
        not in {
            PreparationTaskExecutionState.COMPLETED,
            PreparationTaskExecutionState.SKIPPED,
        }
    )
    if remaining:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_tasks_not_terminal",
                "message": (
                    "Every deterministic task must be explicitly completed or "
                    "skipped before the schedule can be completed"
                ),
                "remaining_task_ids": remaining,
            },
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
    normalized_task_id = task_id.strip()
    if not normalized_task_id:
        raise HTTPException(status_code=404, detail="Resource not found")
    _lock_household(db, household_id)
    fingerprint = _fingerprint(
        schedule_id=schedule_id,
        task_id=normalized_task_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        payload=payload,
    )
    existing = (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(
            DBPreparationTaskExecutionEvent.schedule_id == schedule_id,
            DBPreparationTaskExecutionEvent.idempotency_key
            == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing is not None:
        if (
            existing.household_id != household_id
            or existing.task_id != normalized_task_id
            or existing.event_type != event_type.value
            or existing.request_fingerprint != fingerprint
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "task_event_idempotency_conflict",
                    "message": (
                        "Task execution idempotency key was reused with a "
                        "different request"
                    ),
                },
            )
        schedule = db.get(DBPersistedPreparationSchedule, schedule_id)
        if schedule is None or schedule.household_id != household_id:
            raise HTTPException(status_code=404, detail="Resource not found")
        tasks = _scheduled_tasks(schedule)
        events = _events(db, schedule_id=schedule.id)
        states = _states(tasks, events)
        task = tasks.get(normalized_task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Resource not found")
        return PreparationTaskExecutionMutationView(
            schedule=_schedule_view(schedule),
            task=_task_view(
                task=task,
                state=states[normalized_task_id],
                events=events,
            ),
            event=_event_view(existing),
        )

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
    if schedule.status != PreparationScheduleStatus.APPROVED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "approved_schedule_required",
                "message": "Task execution events require an approved schedule",
                "current_status": schedule.status,
            },
        )
    if schedule.version != payload.expected_schedule_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_version_conflict",
                "message": "Schedule version changed; reload before recording execution",
                "current_version": schedule.version,
            },
        )

    tasks = _scheduled_tasks(schedule)
    task = tasks.get(normalized_task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    horizon = int(schedule.schedule_payload.get("horizon_minutes", 10080))
    if payload.actual_minute > horizon:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "execution_minute_outside_horizon",
                "message": "actual_minute cannot exceed the schedule horizon",
            },
        )

    events = _events(db, schedule_id=schedule.id)
    states = _states(tasks, events)
    current = states[normalized_task_id]
    allowed = {
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
    }
    if current not in allowed[event_type]:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_task_execution_transition",
                "message": (
                    f"Cannot apply {event_type.value} to {current.value} task"
                ),
                "task_id": normalized_task_id,
            },
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
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "task_dependencies_not_terminal",
                    "message": (
                        "Every deterministic dependency must be explicitly "
                        "completed or skipped before this task can start"
                    ),
                    "task_id": normalized_task_id,
                    "blocked_by": blocked,
                },
            )
    if event_type == PreparationTaskExecutionEventType.COMPLETED:
        started_event = next(
            (
                value
                for value in _task_events(events, normalized_task_id)
                if value.event_type
                == PreparationTaskExecutionEventType.STARTED.value
            ),
            None,
        )
        if started_event is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "task_start_event_missing",
                    "message": "Task completion requires an explicit start event",
                    "task_id": normalized_task_id,
                },
            )
        if payload.actual_minute < started_event.actual_minute:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "task_completion_before_start",
                    "message": (
                        "Task completion minute cannot be earlier than its "
                        "confirmed start minute"
                    ),
                    "task_id": normalized_task_id,
                    "started_actual_minute": started_event.actual_minute,
                },
            )

    target = {
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
    deviation = (
        payload.actual_minute - task.start_minute
        if event_type == PreparationTaskExecutionEventType.STARTED
        else payload.actual_minute - task.finish_minute
        if event_type == PreparationTaskExecutionEventType.COMPLETED
        else 0
    )
    if (
        event_type == PreparationTaskExecutionEventType.SKIPPED or deviation != 0
    ) and not payload.reason:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "task_execution_reason_required",
                "message": (
                    "A nonblank reason is required for skipped tasks or timing "
                    "deviations"
                ),
                "task_id": normalized_task_id,
                "deviation_minutes": deviation,
            },
        )

    version_before = schedule.version
    now = utcnow()
    schedule.version += 1
    schedule.updated_at = now
    event = DBPreparationTaskExecutionEvent(
        schedule_id=schedule.id,
        household_id=household_id,
        task_id=normalized_task_id,
        event_type=event_type.value,
        actor_user_id=actor_user_id,
        from_state=current.value,
        to_state=target.value,
        planned_start_minute=task.start_minute,
        planned_finish_minute=task.finish_minute,
        actual_minute=payload.actual_minute,
        deviation_minutes=deviation,
        reason=payload.reason,
        notes=payload.notes,
        event_metadata=payload.metadata,
        idempotency_key=payload.idempotency_key,
        request_fingerprint=fingerprint,
        schedule_version_before=version_before,
        schedule_version_after=schedule.version,
        created_at=now,
    )
    db.add(schedule)
    db.add(event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "task_execution_conflict",
                "message": "Task execution conflicted with concurrent state",
            },
        ) from exc
    db.refresh(schedule)
    db.refresh(event)
    all_events = _events(db, schedule_id=schedule.id)
    return PreparationTaskExecutionMutationView(
        schedule=_schedule_view(schedule),
        task=_task_view(
            task=task,
            state=target,
            events=all_events,
        ),
        event=_event_view(event),
    )
