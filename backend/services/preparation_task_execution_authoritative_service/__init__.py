"""Final authoritative task-execution validation entry point.

This package shadows the sibling implementation and adds cross-record identity
checks before delegating to its complete task/state/timing/version validator.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionMutationView,
    PreparationTaskExecutionOverview,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent


_LEGACY_PATH = Path(__file__).resolve().parent.parent / "preparation_task_execution_authoritative_service.py"
_LEGACY_SPEC = importlib.util.spec_from_file_location(
    "backend.services._legacy_preparation_task_execution_authoritative_service",
    _LEGACY_PATH,
)
if _LEGACY_SPEC is None or _LEGACY_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError("Task execution authoritative implementation is unavailable")
_LEGACY_MODULE = importlib.util.module_from_spec(_LEGACY_SPEC)
_LEGACY_SPEC.loader.exec_module(_LEGACY_MODULE)


def _conflict(code: str, message: str, **details) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": message, **details},
    )


def _validate_cross_record_identity(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> None:
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
    events = (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(DBPreparationTaskExecutionEvent.schedule_id == schedule_id)
        .order_by(
            DBPreparationTaskExecutionEvent.created_at,
            DBPreparationTaskExecutionEvent.id,
        )
        .all()
    )
    mismatched = [
        value.id for value in events if value.household_id != household_id
    ]
    if mismatched:
        raise _conflict(
            "execution_event_household_mismatch",
            "Persisted task execution events do not belong to the schedule household",
            schedule_id=schedule_id,
            event_ids=mismatched,
        )
    if events and schedule.status == "draft":
        raise _conflict(
            "execution_event_schedule_status_invalid",
            "Draft schedules cannot contain task execution events",
            schedule_id=schedule_id,
        )
    if events and events[0].schedule_version_before < 2:
        raise _conflict(
            "execution_event_version_chain_invalid",
            "Task execution history begins before an approved schedule version",
            schedule_id=schedule_id,
            first_schedule_version=events[0].schedule_version_before,
        )
    future_versions = [
        value.id
        for value in events
        if value.schedule_version_after > schedule.version
    ]
    if future_versions:
        raise _conflict(
            "execution_event_version_chain_invalid",
            "Task execution history references a schedule version newer than the schedule row",
            schedule_id=schedule_id,
            event_ids=future_versions,
            current_schedule_version=schedule.version,
        )


def validate_task_execution_snapshot(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
):
    _validate_cross_record_identity(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    return _LEGACY_MODULE.validate_task_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )


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
    return _LEGACY_MODULE.get_task_execution_overview(
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
    result = _LEGACY_MODULE.record_task_execution_event(
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


__all__ = [
    "get_task_execution_overview",
    "record_task_execution_event",
    "validate_task_execution_snapshot",
]
