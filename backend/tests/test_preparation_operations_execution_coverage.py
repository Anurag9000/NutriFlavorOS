from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBUser, utcnow
from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    PreparationScheduleStatus,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
)
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_operations_coverage_service import (
    get_preparation_operations_coverage,
)
from backend.services.preparation_operations_service import (
    create_persisted_schedule,
    register_resource_calendar,
    transition_schedule,
)
from backend.services.preparation_task_completion_service import (
    complete_schedule_with_execution_guard,
)
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from backend.tests.test_preparation_operations_service import (
    calendar_payload,
    persisted_payload,
    transition_payload,
)


OWNER_ID = "coverage-owner@example.test"
HOUSEHOLD_ID = "coverage-home"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    owner = DBUser(
        id=OWNER_ID,
        name="Coverage owner",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    household = DBHousehold(
        id=HOUSEHOLD_ID,
        owner_user_id=owner.id,
        name="Coverage home",
        timezone="UTC",
        version=1,
    )
    session.add_all([owner, household])
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _approved_schedule(db, suffix: str = "primary"):
    calendar = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload(
            f"coverage-calendar-{suffix}",
            f"coverage-calendar-key-{suffix}",
        ),
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
            "Approved for execution coverage testing",
        ),
    )


def _event(
    version: int,
    actual_minute: int,
    key: str,
    *,
    reason: str | None = None,
):
    return PreparationTaskExecutionEventCreate.model_validate(
        {
            "expected_schedule_version": version,
            "actual_minute": actual_minute,
            "reason": reason,
            "notes": "Coverage fixture event",
            "idempotency_key": key,
            "metadata": {"source": "coverage_test"},
        }
    )


def test_execution_coverage_tracks_states_events_and_deviations(db):
    approved = _approved_schedule(db)
    tasks = approved.schedule.scheduled
    initial = get_preparation_operations_coverage(
        db,
        household_id=HOUSEHOLD_ID,
    )
    assert initial.execution_scope_schedule_count == 1
    assert initial.execution_active_schedule_count == 1
    assert initial.execution_history_schedule_count == 0
    assert initial.execution_invalid_schedule_count == 0
    assert initial.deterministic_task_count == len(tasks)
    assert initial.task_state_counts == {
        "planned": len(tasks),
        "in_progress": 0,
        "completed": 0,
        "skipped": 0,
    }
    assert initial.terminal_task_count == 0
    assert initial.task_event_total == 0
    assert initial.task_event_schedule_coverage == 0.0
    assert initial.terminal_task_coverage == 0.0
    assert initial.latest_task_event_at is None

    first = tasks[0]
    started = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=first.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=_event(
            approved.version,
            first.start_minute,
            "coverage-first-start",
        ),
    )
    completed = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=first.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.COMPLETED,
        payload=_event(
            started.schedule.version,
            first.finish_minute + 5,
            "coverage-first-complete",
            reason="Household completed five minutes after the plan",
        ),
    )
    second = tasks[1]
    skipped = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=second.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.SKIPPED,
        payload=_event(
            completed.schedule.version,
            second.start_minute,
            "coverage-second-skip",
            reason="Household explicitly skipped the second task",
        ),
    )

    terminal = get_preparation_operations_coverage(
        db,
        household_id=HOUSEHOLD_ID,
    )
    assert terminal.execution_history_schedule_count == 1
    assert terminal.task_state_counts == {
        "planned": 0,
        "in_progress": 0,
        "completed": 1,
        "skipped": 1,
    }
    assert terminal.terminal_task_count == 2
    assert terminal.fully_terminal_schedule_count == 1
    assert terminal.task_event_total == 3
    assert terminal.nonzero_deviation_event_count == 1
    assert terminal.skipped_task_event_count == 1
    assert terminal.skip_reason_count == 1
    assert terminal.task_event_schedule_coverage == 1.0
    assert terminal.terminal_task_coverage == 1.0
    assert terminal.latest_task_event_at is not None

    completed_schedule = complete_schedule_with_execution_guard(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        actor_user_id=OWNER_ID,
        payload=transition_payload(
            skipped.schedule.version,
            "coverage-complete-schedule",
            "All deterministic tasks are terminal",
        ),
    )
    assert completed_schedule.status == PreparationScheduleStatus.COMPLETED
    historical = get_preparation_operations_coverage(
        db,
        household_id=HOUSEHOLD_ID,
    )
    assert historical.execution_scope_schedule_count == 1
    assert historical.execution_active_schedule_count == 0
    assert historical.fully_terminal_schedule_count == 1


def test_structurally_invalid_execution_history_is_warned_not_hidden(db):
    approved = _approved_schedule(db, "invalid-history")
    task = approved.schedule.scheduled[0]
    now = utcnow()
    db.add(
        DBPreparationTaskExecutionEvent(
            schedule_id=approved.id,
            household_id=HOUSEHOLD_ID,
            task_id=task.task_id,
            event_type=PreparationTaskExecutionEventType.COMPLETED.value,
            actor_user_id=OWNER_ID,
            from_state="in_progress",
            to_state="completed",
            planned_start_minute=task.start_minute,
            planned_finish_minute=task.finish_minute,
            actual_minute=task.finish_minute,
            deviation_minutes=0,
            reason=None,
            notes="Deliberately inconsistent history fixture",
            event_metadata={"source": "coverage_test"},
            idempotency_key="coverage-invalid-history",
            request_fingerprint="f" * 64,
            schedule_version_before=approved.version,
            schedule_version_after=approved.version + 1,
            created_at=now,
        )
    )
    db.commit()

    coverage = get_preparation_operations_coverage(
        db,
        household_id=HOUSEHOLD_ID,
    )
    assert coverage.execution_scope_schedule_count == 1
    assert coverage.execution_history_schedule_count == 1
    assert coverage.execution_invalid_schedule_count == 1
    assert coverage.deterministic_task_count == 0
    assert coverage.terminal_task_count == 0
    assert any("structurally invalid" in value for value in coverage.warnings)


def test_execution_coverage_is_household_isolated(db):
    coverage = get_preparation_operations_coverage(
        db,
        household_id="other-home",
    )
    assert coverage.schedule_total == 0
    assert coverage.execution_scope_schedule_count == 0
    assert coverage.task_event_total == 0
    assert coverage.deterministic_task_count == 0
    assert coverage.task_event_schedule_coverage == 0.0
    assert coverage.terminal_task_coverage == 0.0
