from __future__ import annotations

from backend.database import utcnow
from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    PreparationScheduleStatus,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.services.preparation_operations_coverage_service import (
    get_preparation_operations_coverage,
)
from backend.services.preparation_operations_service import (
    create_persisted_schedule,
    get_resource_calendar,
    transition_schedule,
)
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
from backend.tests.test_preparation_operations_service import (
    persisted_payload,
    transition_payload,
)


def _approved_schedule_on_existing_calendar(db, source, suffix: str):
    calendar = get_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        calendar_id=source.calendar_version_id,
    )
    draft = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=persisted_payload(
            calendar,
            f"coverage-schedule-key-{suffix}",
            household_id=HOUSEHOLD_ID,
        ),
    )
    return transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            draft.version,
            f"coverage-approve-{suffix}",
            "Approve a second schedule on the same reviewed calendar",
        ),
    )


def test_partial_task_history_gap_is_reported(db):
    first = _approved_schedule(db, "history-first")
    second = _approved_schedule_on_existing_calendar(db, first, "history-second")
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
    assert second.calendar_version_id == first.calendar_version_id


def test_legacy_completed_schedule_without_terminal_task_evidence_is_invalid(db):
    approved = _approved_schedule(db, "legacy-completed")

    # Represent a historical row written before completion authority moved to
    # the lowest service layer. Current transition APIs correctly reject this
    # state, so the fixture must bypass them while still satisfying the database
    # approval/status constraints. Coverage should then classify the row as
    # structurally invalid rather than treating it as executable evidence.
    row = db.get(DBPersistedPreparationSchedule, approved.id)
    row.status = PreparationScheduleStatus.COMPLETED.value
    row.version += 1
    row.updated_at = utcnow()
    db.add(row)
    db.commit()

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
