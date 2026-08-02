from __future__ import annotations

import copy

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBUser
from backend.domain.preparation_operations import PreparationScheduleEventType
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_operations_service import (
    create_persisted_schedule,
    register_resource_calendar,
    transition_schedule,
)
from backend.services.preparation_task_execution_authoritative_service import (
    get_task_execution_overview,
)
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from backend.tests.test_preparation_operations_service import (
    calendar_payload,
    persisted_payload,
    transition_payload,
)


HOUSEHOLD_ID = "authoritative-execution-home"
OWNER_ID = "authoritative-owner@example.test"


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
        name="Authoritative owner",
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
        name="Authoritative execution home",
        timezone="UTC",
        version=1,
    )
    session.add_all([owner, household])
    session.commit()
    try:
        yield session
    finally:
        session.close()


def approved_schedule(db):
    calendar = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload(
            "authoritative-calendar-v1",
            "authoritative-calendar-key-v1",
        ),
    )
    draft = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=persisted_payload(
            calendar,
            "authoritative-schedule-key-v1",
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
            "authoritative-approve-v1",
            "Approve authoritative validation fixture",
        ),
    )


def event_payload(
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
            "notes": "Authoritative validation fixture",
            "idempotency_key": key,
            "metadata": {"source": "authoritative_test"},
        }
    )


def test_unknown_persisted_dependency_is_a_controlled_conflict(db):
    approved = approved_schedule(db)
    row = db.get(DBPersistedPreparationSchedule, approved.id)
    payload = copy.deepcopy(row.schedule_payload)
    payload["scheduled"][0]["dependencies"] = ["missing.task"]
    row.schedule_payload = payload
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_task_execution_overview(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "persisted_schedule_dependency_missing"
    assert exc.value.detail["unknown_dependency_ids"] == ["missing.task"]


def test_event_planned_time_snapshot_drift_is_rejected(db):
    approved = approved_schedule(db)
    task = approved.schedule.scheduled[0]
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
            "authoritative-snapshot-start",
        ),
    )
    row = db.get(DBPreparationTaskExecutionEvent, started.event.id)
    row.planned_start_minute += 1
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_task_execution_overview(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
        )
    assert exc.value.detail["code"] == "execution_event_plan_snapshot_mismatch"


def test_broken_task_event_version_chain_is_rejected(db):
    approved = approved_schedule(db)
    task = approved.schedule.scheduled[0]
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
            "authoritative-chain-start",
        ),
    )
    completed = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.COMPLETED,
        payload=event_payload(
            started.schedule.version,
            task.finish_minute,
            "authoritative-chain-complete",
        ),
    )
    row = db.get(DBPreparationTaskExecutionEvent, completed.event.id)
    row.schedule_version_before += 1
    row.schedule_version_after += 1
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_task_execution_overview(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
        )
    assert exc.value.detail["code"] == "execution_event_version_chain_invalid"


def test_approved_schedule_latest_task_event_version_must_match(db):
    approved = approved_schedule(db)
    task = approved.schedule.scheduled[0]
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
            "authoritative-latest-start",
        ),
    )
    schedule = db.get(DBPersistedPreparationSchedule, approved.id)
    schedule.version = started.schedule.version + 1
    db.add(schedule)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_task_execution_overview(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
        )
    assert exc.value.detail["code"] == "execution_event_version_chain_invalid"
