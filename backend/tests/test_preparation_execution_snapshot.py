from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBUser
from backend.domain.preparation_operations import PreparationScheduleEventType
from backend.domain.preparation_task_execution import PreparationTaskExecutionEventType
from backend.services.preparation_execution_snapshot_service import (
    assert_execution_aware_supersession_allowed,
    assert_preparation_execution_snapshot_unchanged,
    get_preparation_execution_snapshot,
)
from backend.services.preparation_operations_service import (
    create_persisted_schedule,
    register_resource_calendar,
    transition_schedule,
)
from backend.services.preparation_task_execution_service import (
    get_task_execution_overview,
    record_task_execution_event,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    calendar_payload,
    persisted_payload,
    transition_payload,
)
from backend.tests.test_preparation_task_execution_service import event_payload


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
        name="Owner",
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
        name="Execution snapshot home",
        timezone="UTC",
        version=1,
    )
    session.add_all([owner, household])
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _approved_schedule(db):
    calendar = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload(
            "execution-snapshot-v1",
            "execution-snapshot-calendar-v1",
        ),
    )
    draft = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=persisted_payload(calendar, "execution-snapshot-schedule-v1"),
    )
    return transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            draft.version,
            "execution-snapshot-approve-v1",
            "Approve schedule for execution snapshot tests",
        ),
    )


def test_snapshot_hash_ignores_capture_time_but_binds_schedule_state(db):
    approved = _approved_schedule(db)
    first = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    second = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )

    assert first.execution_event_count == 0
    assert first.latest_execution_event_id is None
    assert first.frozen_task_ids == []
    assert first.in_progress_task_ids == []
    assert first.repairable_task_ids
    assert first.execution_snapshot_hash == second.execution_snapshot_hash
    assert first.execution_event_ledger_hash == second.execution_event_ledger_hash


def test_execution_event_changes_snapshot_and_stale_identity_fails_closed(db):
    approved = _approved_schedule(db)
    before = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    overview = get_task_execution_overview(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    task = next(value.task for value in overview.tasks if not value.task.dependencies)

    started = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            task.start_minute,
            "execution-snapshot-start-v1",
        ),
    )
    after = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )

    assert after.execution_event_count == 1
    assert after.latest_execution_event_id == started.event.id
    assert after.in_progress_task_ids == [task.task_id]
    assert task.task_id not in after.repairable_task_ids
    assert after.execution_snapshot_hash != before.execution_snapshot_hash
    assert after.execution_event_ledger_hash != before.execution_event_ledger_hash

    with pytest.raises(HTTPException) as exc:
        assert_preparation_execution_snapshot_unchanged(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            expected_execution_snapshot_hash=before.execution_snapshot_hash,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_execution_snapshot_changed"

    with pytest.raises(HTTPException) as exc:
        assert_execution_aware_supersession_allowed(after)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_execution_snapshot_has_in_progress_tasks"


def test_terminal_source_task_is_frozen_and_not_repairable(db):
    approved = _approved_schedule(db)
    overview = get_task_execution_overview(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    task = next(value.task for value in overview.tasks if not value.task.dependencies)
    started = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            task.start_minute,
            "execution-snapshot-start-terminal-v1",
        ),
    )
    record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.COMPLETED,
        payload=event_payload(
            started.schedule.version,
            task.finish_minute,
            "execution-snapshot-complete-terminal-v1",
        ),
    )

    snapshot = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    assert task.task_id in snapshot.frozen_task_ids
    assert task.task_id not in snapshot.repairable_task_ids
    assert snapshot.in_progress_task_ids == []
    assert_execution_aware_supersession_allowed(snapshot)
