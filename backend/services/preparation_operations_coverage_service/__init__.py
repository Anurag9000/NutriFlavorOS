"""Authoritative preparation coverage entry point.

This package shadows the historical sibling module, reuses its operational
provenance calculation, and recomputes task-execution denominators from the
strict product-facing snapshot validator.
"""

from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation_operations import PreparationScheduleStatus
from backend.domain.preparation_operations_coverage import (
    PreparationOperationsCoverageView,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionState,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_task_execution_authoritative_service import (
    validate_task_execution_snapshot,
)


_LEGACY_PATH = Path(__file__).resolve().parent.parent / "preparation_operations_coverage_service.py"
_LEGACY_SPEC = importlib.util.spec_from_file_location(
    "backend.services._legacy_preparation_operations_coverage_service",
    _LEGACY_PATH,
)
if _LEGACY_SPEC is None or _LEGACY_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError("Legacy preparation coverage service is unavailable")
_LEGACY_MODULE = importlib.util.module_from_spec(_LEGACY_SPEC)
_LEGACY_SPEC.loader.exec_module(_LEGACY_MODULE)


SCOPE_STATUSES = {
    PreparationScheduleStatus.APPROVED.value,
    PreparationScheduleStatus.COMPLETED.value,
}
TERMINAL_STATES = {
    PreparationTaskExecutionState.COMPLETED,
    PreparationTaskExecutionState.SKIPPED,
}


def _ratio(value: int, total: int) -> float:
    return round(value / total, 6) if total else 0.0


def get_preparation_operations_coverage(
    db: Session,
    *,
    household_id: str,
) -> PreparationOperationsCoverageView:
    base = _LEGACY_MODULE.get_preparation_operations_coverage(
        db,
        household_id=household_id,
    )
    schedules = (
        db.query(DBPersistedPreparationSchedule)
        .filter(DBPersistedPreparationSchedule.household_id == household_id)
        .order_by(DBPersistedPreparationSchedule.id)
        .all()
    )
    events = (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(DBPreparationTaskExecutionEvent.household_id == household_id)
        .order_by(
            DBPreparationTaskExecutionEvent.created_at,
            DBPreparationTaskExecutionEvent.id,
        )
        .all()
    )
    event_schedule_ids = {value.schedule_id for value in events}
    scope = [
        value
        for value in schedules
        if value.status in SCOPE_STATUSES or value.id in event_schedule_ids
    ]

    state_counts = Counter(
        {
            PreparationTaskExecutionState.PLANNED.value: 0,
            PreparationTaskExecutionState.IN_PROGRESS.value: 0,
            PreparationTaskExecutionState.COMPLETED.value: 0,
            PreparationTaskExecutionState.SKIPPED.value: 0,
        }
    )
    invalid_count = 0
    deterministic_task_count = 0
    terminal_task_count = 0
    fully_terminal_schedule_count = 0
    history_schedule_count = sum(value.id in event_schedule_ids for value in scope)

    for schedule in scope:
        try:
            _, tasks, _, states = validate_task_execution_snapshot(
                db,
                household_id=household_id,
                schedule_id=schedule.id,
            )
        except HTTPException:
            invalid_count += 1
            continue
        terminal = sum(value in TERMINAL_STATES for value in states.values())
        if (
            schedule.status == PreparationScheduleStatus.COMPLETED.value
            and terminal != len(tasks)
        ):
            invalid_count += 1
            continue
        deterministic_task_count += len(tasks)
        terminal_task_count += terminal
        state_counts.update(value.value for value in states.values())
        fully_terminal_schedule_count += int(terminal == len(tasks))

    nonzero_deviation_count = sum(value.deviation_minutes != 0 for value in events)
    skipped_count = sum(
        value.event_type == PreparationTaskExecutionEventType.SKIPPED.value
        for value in events
    )
    skip_reason_count = sum(
        value.event_type == PreparationTaskExecutionEventType.SKIPPED.value
        and bool(value.reason and value.reason.strip())
        for value in events
    )

    warnings = [
        value
        for value in base.warnings
        if value
        not in {
            "Approved or completed execution schedules have no task-event history",
            "One or more execution schedules or task histories are structurally invalid",
        }
    ]
    if scope and history_schedule_count < len(scope):
        warnings.append(
            "One or more execution-scope schedules have no task-event history"
        )
    if invalid_count:
        warnings.append(
            "One or more execution schedules or task histories are structurally invalid"
        )
    if skipped_count != skip_reason_count and (
        "One or more skipped task events lack a nonblank reason" not in warnings
    ):
        warnings.append("One or more skipped task events lack a nonblank reason")

    payload = base.model_dump(mode="json")
    payload.update(
        {
            "execution_scope_schedule_count": len(scope),
            "execution_active_schedule_count": sum(
                value.status == PreparationScheduleStatus.APPROVED.value
                for value in scope
            ),
            "execution_history_schedule_count": history_schedule_count,
            "execution_invalid_schedule_count": invalid_count,
            "deterministic_task_count": deterministic_task_count,
            "task_state_counts": {
                state.value: int(state_counts.get(state.value, 0))
                for state in PreparationTaskExecutionState
            },
            "terminal_task_count": terminal_task_count,
            "fully_terminal_schedule_count": fully_terminal_schedule_count,
            "task_event_total": len(events),
            "nonzero_deviation_event_count": nonzero_deviation_count,
            "skipped_task_event_count": skipped_count,
            "skip_reason_count": skip_reason_count,
            "task_event_schedule_coverage": _ratio(
                history_schedule_count,
                len(scope),
            ),
            "terminal_task_coverage": _ratio(
                terminal_task_count,
                deterministic_task_count,
            ),
            "latest_task_event_at": (
                events[-1].created_at.isoformat() if events else None
            ),
            "warnings": warnings,
        }
    )
    return PreparationOperationsCoverageView.model_validate(payload)


__all__ = ["get_preparation_operations_coverage"]
