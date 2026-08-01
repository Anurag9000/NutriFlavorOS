from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBUser
from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    PreparationScheduleEventType,
    PreparationScheduleStatus,
    ResourceCalendarVersionCreate,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.services.preparation_operations_service import (
    create_persisted_schedule,
    list_resource_calendars,
    list_schedule_events,
    register_resource_calendar,
    transition_schedule,
)


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
        id="owner@example.test",
        name="Owner",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    household = DBHousehold(
        id="prep-home",
        owner_user_id=owner.id,
        name="Preparation home",
        timezone="UTC",
        version=1,
    )
    session.add_all([owner, household])
    session.commit()
    try:
        yield session
    finally:
        session.close()


def calendar_payload(
    version: str,
    key: str,
    *,
    activate: bool = True,
    second_window_start: int = 60,
) -> ResourceCalendarVersionCreate:
    return ResourceCalendarVersionCreate.model_validate(
        {
            "calendar_version": version,
            "horizon_minutes": 180,
            "timezone": "UTC",
            "resources": [
                {
                    "resource_id": "person",
                    "label": "Available cook",
                    "capacity": 1,
                    "resource_kind": "person",
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 30},
                        {"start_minute": second_window_start, "end_minute": 150},
                    ],
                    "metadata": {"review_scope": "test"},
                },
                {
                    "resource_id": "burner",
                    "label": "Burner",
                    "capacity": 1,
                    "resource_kind": "equipment",
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 150}
                    ],
                    "metadata": {},
                },
            ],
            "evidence_status": CalendarEvidenceStatus.REVIEWED.value,
            "reviewed_at": "2026-08-01T00:00:00Z",
            "reviewed_by": "Calendar reviewer",
            "notes": "Reviewed household fixture",
            "activate": activate,
            "idempotency_key": key,
        }
    )


def schedule_request(calendar) -> PreparationScheduleRequest:
    return PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": calendar.horizon_minutes,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": value.resource_id,
                    "label": value.label,
                    "capacity": value.capacity,
                    "availability_windows": [
                        window.model_dump(mode="json")
                        for window in value.availability_windows
                    ],
                }
                for value in calendar.resources
            ],
            "tasks": [
                {
                    "task_id": "prep",
                    "duration_minutes": 15,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 30,
                    "priority": 2,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {"profile_content_hash": "a" * 64},
                },
                {
                    "task_id": "cook",
                    "duration_minutes": 20,
                    "earliest_start_minute": 60,
                    "latest_finish_minute": 150,
                    "priority": 1,
                    "resource_demands": {"person": 1, "burner": 1},
                    "dependencies": ["prep"],
                    "metadata": {"profile_content_hash": "a" * 64},
                },
            ],
        }
    )


def persisted_payload(calendar, key: str = "persisted-schedule-0001"):
    request = schedule_request(calendar)
    response = build_preparation_schedule(request)
    return PersistedScheduleCreateRequest.model_validate(
        {
            "calendar_version_id": calendar.id,
            "source_plan_id": None,
            "source_plan_version": None,
            "occurrence_set_version": "fixture-v1",
            "occurrence_set_hash": "b" * 64,
            "profile_versions": {
                "fixture-recipe": "profile:1/version:1/sha256:" + "a" * 64
            },
            "schedule_request": request.model_dump(mode="json"),
            "schedule_response": response.model_dump(mode="json"),
            "notes": "Persisted fixture schedule",
            "idempotency_key": key,
        }
    )


def transition_payload(version: int, key: str, reason: str):
    return ScheduleStateTransitionRequest.model_validate(
        {
            "expected_version": version,
            "reason": reason,
            "idempotency_key": key,
            "metadata": {"fixture": True},
        }
    )


def test_calendar_registration_is_immutable_idempotent_and_versioned(db):
    first = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload("v1", "calendar-create-v1"),
    )
    retry = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload("v1", "calendar-create-v1"),
    )
    assert retry.id == first.id
    assert retry.content_hash == first.content_hash
    assert retry.active is True
    assert len(retry.resources) == 2
    assert len(retry.content_hash) == 64

    with pytest.raises(HTTPException) as exc:
        register_resource_calendar(
            db,
            household_id="prep-home",
            actor_user_id="owner@example.test",
            payload=calendar_payload(
                "v1",
                "calendar-create-v1",
                second_window_start=65,
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "calendar_idempotency_conflict"

    all_versions = list_resource_calendars(db, household_id="prep-home")
    assert [value.id for value in all_versions] == [first.id]


def test_schedule_creation_replays_exactly_and_writes_created_event(db):
    calendar = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload("v1", "calendar-create-v1"),
    )
    payload = persisted_payload(calendar)
    schedule = create_persisted_schedule(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=payload,
    )
    retry = create_persisted_schedule(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=payload,
    )
    assert retry.id == schedule.id
    assert schedule.status == PreparationScheduleStatus.DRAFT
    assert schedule.version == 1
    assert schedule.calendar_content_hash == calendar.content_hash
    assert len(schedule.schedule_hash) == 64
    assert schedule.schedule.unscheduled == []

    events = list_schedule_events(
        db,
        household_id="prep-home",
        schedule_id=schedule.id,
    )
    assert len(events) == 1
    assert events[0].event_type == PreparationScheduleEventType.CREATED
    assert events[0].from_status is None
    assert events[0].to_status == PreparationScheduleStatus.DRAFT
    assert events[0].metadata["schedule_hash"] == schedule.schedule_hash


def test_schedule_rejects_calendar_resource_and_replay_mismatch(db):
    calendar = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload("v1", "calendar-create-v1"),
    )
    payload = persisted_payload(calendar)
    mismatched_request = payload.schedule_request.model_copy(deep=True)
    mismatched_request.resources[0].capacity = 2
    mismatch = payload.model_copy(
        update={
            "schedule_request": mismatched_request,
            "idempotency_key": "schedule-resource-mismatch",
        }
    )
    with pytest.raises(HTTPException) as exc:
        create_persisted_schedule(
            db,
            household_id="prep-home",
            actor_user_id="owner@example.test",
            payload=mismatch,
        )
    assert exc.value.detail["code"] == "calendar_resource_mismatch"

    forged_response = payload.schedule_response.model_copy(deep=True)
    forged_response.scheduled[0].start_minute += 5
    forged_response.scheduled[0].finish_minute += 5
    forged = payload.model_copy(
        update={
            "schedule_response": forged_response,
            "idempotency_key": "schedule-replay-mismatch",
        }
    )
    with pytest.raises(HTTPException) as exc:
        create_persisted_schedule(
            db,
            household_id="prep-home",
            actor_user_id="owner@example.test",
            payload=forged,
        )
    assert exc.value.detail["code"] == "schedule_replay_mismatch"


def test_approval_is_optimistic_retry_safe_and_terminal_transitions_are_guarded(db):
    calendar = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload("v1", "calendar-create-v1"),
    )
    schedule = create_persisted_schedule(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=persisted_payload(calendar),
    )
    approval = transition_payload(
        1,
        "approve-schedule-0001",
        "Owner reviewed the calendar and preparation sequence",
    )
    approved = transition_schedule(
        db,
        household_id="prep-home",
        schedule_id=schedule.id,
        actor_user_id="owner@example.test",
        event_type=PreparationScheduleEventType.APPROVED,
        payload=approval,
    )
    retry = transition_schedule(
        db,
        household_id="prep-home",
        schedule_id=schedule.id,
        actor_user_id="owner@example.test",
        event_type=PreparationScheduleEventType.APPROVED,
        payload=approval,
    )
    assert approved.status == PreparationScheduleStatus.APPROVED
    assert approved.version == 2
    assert retry.version == 2
    assert retry.approved_by_user_id == "owner@example.test"

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id="prep-home",
            schedule_id=schedule.id,
            actor_user_id="owner@example.test",
            event_type=PreparationScheduleEventType.COMPLETED,
            payload=transition_payload(
                1,
                "complete-with-stale-version",
                "Attempt with stale version",
            ),
        )
    assert exc.value.detail["code"] == "schedule_version_conflict"

    completed = transition_schedule(
        db,
        household_id="prep-home",
        schedule_id=schedule.id,
        actor_user_id="owner@example.test",
        event_type=PreparationScheduleEventType.COMPLETED,
        payload=transition_payload(
            2,
            "complete-schedule-0001",
            "Household confirmed all preparation tasks completed",
        ),
    )
    assert completed.status == PreparationScheduleStatus.COMPLETED
    assert completed.version == 3

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id="prep-home",
            schedule_id=schedule.id,
            actor_user_id="owner@example.test",
            event_type=PreparationScheduleEventType.CANCELLED,
            payload=transition_payload(
                3,
                "cancel-completed-schedule",
                "Terminal schedule cannot be cancelled",
            ),
        )
    assert exc.value.detail["code"] == "invalid_schedule_transition"


def test_activating_successor_calendar_invalidates_draft_and_approved_schedules(db):
    first_calendar = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload("v1", "calendar-create-v1"),
    )
    draft = create_persisted_schedule(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=persisted_payload(first_calendar, "draft-schedule-v1"),
    )
    approved = create_persisted_schedule(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=persisted_payload(first_calendar, "approved-schedule-v1"),
    )
    approved = transition_schedule(
        db,
        household_id="prep-home",
        schedule_id=approved.id,
        actor_user_id="owner@example.test",
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            approved.version,
            "approve-before-calendar-change",
            "Approve before calendar replacement",
        ),
    )

    second_calendar = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload(
            "v2",
            "calendar-create-v2",
            second_window_start=70,
        ),
    )
    assert second_calendar.active is True
    assert second_calendar.supersedes_calendar_id == first_calendar.id
    assert db.get(DBResourceCalendarVersion, first_calendar.id).active is False

    draft_row = db.get(DBPersistedPreparationSchedule, draft.id)
    approved_row = db.get(DBPersistedPreparationSchedule, approved.id)
    assert draft_row.status == PreparationScheduleStatus.INVALIDATED.value
    assert approved_row.status == PreparationScheduleStatus.INVALIDATED.value
    assert draft_row.version == 2
    assert approved_row.version == 3
    assert str(second_calendar.id) in draft_row.invalidation_reason
    assert str(second_calendar.id) in approved_row.invalidation_reason

    for schedule_id in (draft.id, approved.id):
        events = (
            db.query(DBPreparationScheduleEvent)
            .filter(DBPreparationScheduleEvent.schedule_id == schedule_id)
            .order_by(DBPreparationScheduleEvent.id)
            .all()
        )
        assert events[-1].event_type == PreparationScheduleEventType.INVALIDATED.value
        assert events[-1].event_metadata["replacement_calendar_id"] == second_calendar.id


def test_schedule_cannot_be_created_against_inactive_or_draft_calendar(db):
    reviewed = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload("v1", "calendar-create-v1"),
    )
    register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload("v2", "calendar-create-v2", second_window_start=70),
    )
    with pytest.raises(HTTPException) as exc:
        create_persisted_schedule(
            db,
            household_id="prep-home",
            actor_user_id="owner@example.test",
            payload=persisted_payload(reviewed, "inactive-calendar-schedule"),
        )
    assert exc.value.detail["code"] == "active_reviewed_calendar_required"

    draft_payload = calendar_payload(
        "draft-v1",
        "calendar-draft-v1",
        activate=False,
    ).model_copy(
        update={
            "evidence_status": CalendarEvidenceStatus.DRAFT,
            "reviewed_at": None,
            "reviewed_by": None,
        }
    )
    draft_calendar = register_resource_calendar(
        db,
        household_id="prep-home",
        actor_user_id="owner@example.test",
        payload=draft_payload,
    )
    with pytest.raises(HTTPException) as exc:
        create_persisted_schedule(
            db,
            household_id="prep-home",
            actor_user_id="owner@example.test",
            payload=persisted_payload(draft_calendar, "draft-calendar-schedule"),
        )
    assert exc.value.detail["code"] == "active_reviewed_calendar_required"
