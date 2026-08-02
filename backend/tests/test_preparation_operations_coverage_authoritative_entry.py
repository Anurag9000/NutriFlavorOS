from __future__ import annotations

from backend.domain.preparation_operations import PreparationScheduleEventType
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
)
from backend.services.preparation_operations_coverage_service import (
    get_preparation_operations_coverage,
)
from backend.services.preparation_operations_service import transition_schedule
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from backend.tests.test_preparation_operations_execution_coverage import (
    HOUSEHOLD_ID,
    OWNER_ID,
    _approved_schedule,
    _event,
    db,
)
from backend.tests.test_preparation_operations_service import transition_payload


def test_partial_task_history_gap_is_reported(db):
    first = _approved_schedule(db, "history-first")
    second = _approved_schedule(db, "history-second")
    task = first.schedule.scheduled[0]
    record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=first.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=_event(
            first.version,
            task.start_minute,
            "coverage-partial-history-start",
        ),
    )

    coverage = get_preparation_operations_coverage(
        db,
        household_id=HOUSEHOLD_ID,
    )
    assert coverage.execution_scope_schedule_count == 2
    assert coverage.execution_history_schedule_count == 1
    assert coverage.task_event_schedule_coverage == 0.5
    assert any("have no task-event history" in value for value in coverage.warnings)
    assert second.id != first.id


def test_legacy_completed_schedule_without_terminal_task_evidence_is_invalid(db):
    approved = _approved_schedule(db, "legacy-completed")
    completed = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.COMPLETED,
        payload=transition_payload(
            approved.version,
            "coverage-legacy-complete",
            "Historical low-level completion fixture",
        ),
    )
    assert completed.status.value == "completed"

    coverage = get_preparation_operations_coverage(
        db,
        household_id=HOUSEHOLD_ID,
    )
    assert coverage.execution_scope_schedule_count == 1
    assert coverage.execution_invalid_schedule_count == 1
    assert coverage.deterministic_task_count == 0
    assert coverage.terminal_task_count == 0
    assert coverage.fully_terminal_schedule_count == 0
    assert coverage.terminal_task_coverage == 0.0
    assert any("structurally invalid" in value for value in coverage.warnings)
