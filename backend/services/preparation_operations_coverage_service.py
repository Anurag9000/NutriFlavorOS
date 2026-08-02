"""Descriptive provenance and execution coverage for household operations."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.domain.preparation import PreparationScheduleResponse
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    PreparationScheduleStatus,
)
from backend.domain.preparation_operations_coverage import (
    PreparationOperationsCoverageView,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionState,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_operations_service import utcnow


REPLAY_STATUSES = (
    "replayable",
    "legacy_request_missing",
    "legacy_occurrence_set_missing",
)
EXECUTION_SCOPE_STATUSES = {
    PreparationScheduleStatus.APPROVED.value,
    PreparationScheduleStatus.COMPLETED.value,
}
TERMINAL_TASK_STATES = {
    PreparationTaskExecutionState.COMPLETED.value,
    PreparationTaskExecutionState.SKIPPED.value,
}


def _coverage(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def _execution_structure(
    schedules: List[DBPersistedPreparationSchedule],
    events: List[DBPreparationTaskExecutionEvent],
) -> dict:
    events_by_schedule: Dict[int, List[DBPreparationTaskExecutionEvent]] = (
        defaultdict(list)
    )
    for event in events:
        events_by_schedule[event.schedule_id].append(event)

    schedule_ids = {value.id for value in schedules}
    orphan_event_schedule_ids = sorted(set(events_by_schedule) - schedule_ids)
    scope = [
        value
        for value in schedules
        if value.status in EXECUTION_SCOPE_STATUSES
        or value.id in events_by_schedule
    ]
    active_count = sum(
        value.status == PreparationScheduleStatus.APPROVED.value
        for value in scope
    )
    history_count = sum(bool(events_by_schedule.get(value.id)) for value in scope)
    invalid_count = 0
    deterministic_task_count = 0
    terminal_task_count = 0
    fully_terminal_schedule_count = 0
    state_counts = Counter(
        {
            PreparationTaskExecutionState.PLANNED.value: 0,
            PreparationTaskExecutionState.IN_PROGRESS.value: 0,
            PreparationTaskExecutionState.COMPLETED.value: 0,
            PreparationTaskExecutionState.SKIPPED.value: 0,
        }
    )

    invalid_schedule_ids: List[int] = []
    for schedule in scope:
        try:
            response = PreparationScheduleResponse.model_validate(
                schedule.schedule_payload
            )
        except ValidationError:
            invalid_count += 1
            invalid_schedule_ids.append(schedule.id)
            continue
        task_map = {value.task_id: value for value in response.scheduled}
        unknown_dependencies = {
            dependency
            for task in response.scheduled
            for dependency in task.dependencies
            if dependency not in task_map
        }
        if (
            response.unscheduled
            or not response.scheduled
            or len(task_map) != len(response.scheduled)
            or unknown_dependencies
        ):
            invalid_count += 1
            invalid_schedule_ids.append(schedule.id)
            continue

        states = {
            task_id: PreparationTaskExecutionState.PLANNED.value
            for task_id in task_map
        }
        history_valid = True
        for event in events_by_schedule.get(schedule.id, []):
            if event.task_id not in task_map:
                history_valid = False
                break
            if states[event.task_id] != event.from_state:
                history_valid = False
                break
            expected_target = {
                PreparationTaskExecutionEventType.STARTED.value: (
                    PreparationTaskExecutionState.IN_PROGRESS.value
                ),
                PreparationTaskExecutionEventType.COMPLETED.value: (
                    PreparationTaskExecutionState.COMPLETED.value
                ),
                PreparationTaskExecutionEventType.SKIPPED.value: (
                    PreparationTaskExecutionState.SKIPPED.value
                ),
            }.get(event.event_type)
            if expected_target is None or expected_target != event.to_state:
                history_valid = False
                break
            states[event.task_id] = event.to_state
        if not history_valid:
            invalid_count += 1
            invalid_schedule_ids.append(schedule.id)
            continue

        deterministic_task_count += len(states)
        state_counts.update(states.values())
        terminal = sum(value in TERMINAL_TASK_STATES for value in states.values())
        terminal_task_count += terminal
        fully_terminal_schedule_count += int(terminal == len(states))

    task_event_total = len(events)
    nonzero_deviation_event_count = sum(
        value.deviation_minutes != 0 for value in events
    )
    skipped_task_event_count = sum(
        value.event_type == PreparationTaskExecutionEventType.SKIPPED.value
        for value in events
    )
    skip_reason_count = sum(
        value.event_type == PreparationTaskExecutionEventType.SKIPPED.value
        and bool(value.reason and value.reason.strip())
        for value in events
    )

    return {
        "execution_scope_schedule_count": len(scope),
        "execution_active_schedule_count": active_count,
        "execution_history_schedule_count": history_count,
        "execution_invalid_schedule_count": invalid_count,
        "deterministic_task_count": deterministic_task_count,
        "task_state_counts": {
            state.value: int(state_counts.get(state.value, 0))
            for state in PreparationTaskExecutionState
        },
        "terminal_task_count": terminal_task_count,
        "fully_terminal_schedule_count": fully_terminal_schedule_count,
        "task_event_total": task_event_total,
        "nonzero_deviation_event_count": nonzero_deviation_event_count,
        "skipped_task_event_count": skipped_task_event_count,
        "skip_reason_count": skip_reason_count,
        "task_event_schedule_coverage": _coverage(history_count, len(scope)),
        "terminal_task_coverage": _coverage(
            terminal_task_count,
            deterministic_task_count,
        ),
        "latest_task_event_at": (
            events[-1].created_at.isoformat() if events else None
        ),
        "orphan_event_schedule_ids": orphan_event_schedule_ids,
        "invalid_schedule_ids": invalid_schedule_ids,
    }


def get_preparation_operations_coverage(
    db: Session,
    *,
    household_id: str,
) -> PreparationOperationsCoverageView:
    """Summarize stored records without replaying or certifying execution."""

    calendars = (
        db.query(DBResourceCalendarVersion)
        .filter(DBResourceCalendarVersion.household_id == household_id)
        .order_by(
            DBResourceCalendarVersion.created_at.desc(),
            DBResourceCalendarVersion.id.desc(),
        )
        .all()
    )
    schedules = (
        db.query(DBPersistedPreparationSchedule)
        .filter(DBPersistedPreparationSchedule.household_id == household_id)
        .order_by(
            DBPersistedPreparationSchedule.created_at.desc(),
            DBPersistedPreparationSchedule.id.desc(),
        )
        .all()
    )
    event_total = int(
        db.query(func.count(DBPreparationScheduleEvent.id))
        .filter(DBPreparationScheduleEvent.household_id == household_id)
        .scalar()
        or 0
    )
    task_events = (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(DBPreparationTaskExecutionEvent.household_id == household_id)
        .order_by(
            DBPreparationTaskExecutionEvent.created_at,
            DBPreparationTaskExecutionEvent.id,
        )
        .all()
    )

    calendar_total = len(calendars)
    reviewed_calendar_total = sum(
        value.evidence_status == CalendarEvidenceStatus.REVIEWED.value
        for value in calendars
    )
    active_reviewed_calendar_count = sum(
        bool(value.active)
        and value.evidence_status == CalendarEvidenceStatus.REVIEWED.value
        for value in calendars
    )

    schedule_total = len(schedules)
    status_counts = Counter(value.status for value in schedules)
    schedule_status_counts = {
        status.value: int(status_counts.get(status.value, 0))
        for status in PreparationScheduleStatus
    }

    replay_counts = Counter()
    occurrence_document_count = 0
    scheduler_request_count = 0
    replayable_draft_count = 0
    source_plan_linked_count = 0
    for value in schedules:
        has_occurrence = value.occurrence_set_payload is not None
        has_request = (
            value.schedule_request_payload is not None
            and bool(value.schedule_request_hash)
        )
        occurrence_document_count += int(has_occurrence)
        scheduler_request_count += int(has_request)
        source_plan_linked_count += int(
            value.source_plan_id is not None
            and value.source_plan_version is not None
        )
        if not has_request:
            replay_status = "legacy_request_missing"
        elif not has_occurrence:
            replay_status = "legacy_occurrence_set_missing"
        else:
            replay_status = "replayable"
            if value.status == PreparationScheduleStatus.DRAFT.value:
                replayable_draft_count += 1
        replay_counts[replay_status] += 1

    replay_status_counts = {
        status: int(replay_counts.get(status, 0)) for status in REPLAY_STATUSES
    }
    replayable_schedule_count = replay_status_counts["replayable"]
    execution = _execution_structure(schedules, task_events)

    warnings: list[str] = []
    if active_reviewed_calendar_count == 0:
        warnings.append("No active reviewed resource calendar is available")
    elif active_reviewed_calendar_count > 1:
        warnings.append(
            "More than one active reviewed resource calendar was observed"
        )
    if schedule_total == 0:
        warnings.append("No persisted preparation schedules are available")
    if replayable_schedule_count < schedule_total:
        warnings.append(
            "One or more legacy schedules lack complete replay provenance"
        )
    if source_plan_linked_count < schedule_total and schedule_total:
        warnings.append(
            "One or more schedules are not linked to a source plan version"
        )
    if (
        execution["execution_scope_schedule_count"]
        and execution["execution_history_schedule_count"] == 0
    ):
        warnings.append(
            "Approved or completed execution schedules have no task-event history"
        )
    if execution["execution_invalid_schedule_count"]:
        warnings.append(
            "One or more execution schedules or task histories are structurally invalid"
        )
    if execution["orphan_event_schedule_ids"]:
        warnings.append(
            "Task events were observed without a matching household schedule"
        )
    if execution["skipped_task_event_count"] != execution["skip_reason_count"]:
        warnings.append("One or more skipped task events lack a nonblank reason")

    return PreparationOperationsCoverageView(
        household_id=household_id,
        generated_at=utcnow().isoformat(),
        calendar_total=calendar_total,
        reviewed_calendar_total=reviewed_calendar_total,
        active_reviewed_calendar_count=active_reviewed_calendar_count,
        schedule_total=schedule_total,
        schedule_status_counts=schedule_status_counts,
        replay_status_counts=replay_status_counts,
        occurrence_document_count=occurrence_document_count,
        scheduler_request_count=scheduler_request_count,
        replayable_schedule_count=replayable_schedule_count,
        replayable_draft_count=replayable_draft_count,
        source_plan_linked_count=source_plan_linked_count,
        event_total=event_total,
        occurrence_document_coverage=_coverage(
            occurrence_document_count,
            schedule_total,
        ),
        scheduler_request_coverage=_coverage(
            scheduler_request_count,
            schedule_total,
        ),
        replayable_schedule_coverage=_coverage(
            replayable_schedule_count,
            schedule_total,
        ),
        execution_scope_schedule_count=execution[
            "execution_scope_schedule_count"
        ],
        execution_active_schedule_count=execution[
            "execution_active_schedule_count"
        ],
        execution_history_schedule_count=execution[
            "execution_history_schedule_count"
        ],
        execution_invalid_schedule_count=execution[
            "execution_invalid_schedule_count"
        ],
        deterministic_task_count=execution["deterministic_task_count"],
        task_state_counts=execution["task_state_counts"],
        terminal_task_count=execution["terminal_task_count"],
        fully_terminal_schedule_count=execution[
            "fully_terminal_schedule_count"
        ],
        task_event_total=execution["task_event_total"],
        nonzero_deviation_event_count=execution[
            "nonzero_deviation_event_count"
        ],
        skipped_task_event_count=execution["skipped_task_event_count"],
        skip_reason_count=execution["skip_reason_count"],
        task_event_schedule_coverage=execution[
            "task_event_schedule_coverage"
        ],
        terminal_task_coverage=execution["terminal_task_coverage"],
        latest_calendar_created_at=(
            calendars[0].created_at.isoformat() if calendars else None
        ),
        latest_schedule_created_at=(
            schedules[0].created_at.isoformat() if schedules else None
        ),
        latest_task_event_at=execution["latest_task_event_at"],
        warnings=warnings,
    )
