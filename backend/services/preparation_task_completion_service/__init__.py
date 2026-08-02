"""Authoritative guarded schedule completion entry point.

This package intentionally shadows the historical sibling module of the same
base name. It preserves that module's proven lifecycle/idempotency transition
implementation while adding strict task-snapshot validation under the household
lock before delegation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from backend.domain.preparation_operations import (
    PersistedPreparationScheduleView,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_task_execution import PreparationTaskExecutionState
from backend.services.preparation_operations_service import _lock_household
from backend.services.preparation_task_execution_authoritative_service import (
    validate_task_execution_snapshot,
)


_LEGACY_PATH = Path(__file__).resolve().parent.parent / "preparation_task_completion_service.py"
_LEGACY_SPEC = importlib.util.spec_from_file_location(
    "backend.services._legacy_preparation_task_completion_service",
    _LEGACY_PATH,
)
if _LEGACY_SPEC is None or _LEGACY_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError("Legacy preparation task completion service is unavailable")
_LEGACY_MODULE = importlib.util.module_from_spec(_LEGACY_SPEC)
_LEGACY_SPEC.loader.exec_module(_LEGACY_MODULE)


TERMINAL_TASK_STATES = {
    PreparationTaskExecutionState.COMPLETED,
    PreparationTaskExecutionState.SKIPPED,
}


def _legacy_completion_module() -> ModuleType:
    return _LEGACY_MODULE


def complete_schedule_with_execution_guard(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    payload: ScheduleStateTransitionRequest,
) -> PersistedPreparationScheduleView:
    """Complete only after strict, locked, append-only task terminality proof."""

    _lock_household(db, household_id)
    _, tasks, _, states = validate_task_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    remaining = sorted(
        task_id
        for task_id in tasks
        if states[task_id] not in TERMINAL_TASK_STATES
    )
    if remaining:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_tasks_not_terminal",
                "message": (
                    "Every deterministic task must be explicitly completed "
                    "or skipped before schedule completion"
                ),
                "remaining_task_ids": remaining,
            },
        )
    return _legacy_completion_module().complete_schedule_with_execution_guard(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


__all__ = ["complete_schedule_with_execution_guard"]
