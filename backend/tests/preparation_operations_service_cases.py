from __future__ import annotations

from copy import deepcopy

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
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.services.preparation_operations_service import (
    create_persisted_schedule,
    get_persisted_schedule,
    list_resource_calendars,
    list_schedule_events,
    register_resource_calendar,
    transition_schedule,
)


PROFILE_HASH = "a" * 64
HOUSEHOLD_ID = "prep-home"
OWNER_ID = "owner@example.test"


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
                        {
                            "start_minute": second_window_start,
                            "end_minute": 150,
                        },
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


def _task_metadata(
    *,
    template_id: str,
    duration_minutes: int,
    active_work: bool,
) -> dict:
    return {
        "occurrence_id": "dinner",
        "recipe_id": "fixture-recipe",
        "servings": 2.0,
        "profile_id": 1,
        "profile_version": "v1",
        "profile_content_hash": PROFILE_HASH,
        "duration_min_minutes": duration_minutes,
        "duration_max_minutes": duration_minutes,
        "duration_policy": "conservative_max",
        "template_id": template_id,
        "active_work": active_work,
        "unattended_allowed": not active_work,
    }


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
                    "task_id": "dinner.prep",
                    "duration_minutes": 15,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 150,
                    "priority": 2,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": _task_metadata(
                        template_id="prep",
                        duration_minutes=15,
                        active_work=True,
                    ),
                },
                {
                    "task_id": "dinner.cook",
                    "duration_minutes": 20,
                    "earliest_start_minute": 60,
                    "latest_finish_minute": 150,
                    "priority": 2,
                    "resource_demands": {"person": 1, "burner": 1},
                    "dependencies": ["dinner.prep"],
                    "metadata": _task_metadata(
                        template_id="cook",
                        duration_minutes=20,
                        active_work=True,
                    ),
                },
            ],
        }
    )


def persisted_payload(
    calendar,
    key: str = "persisted-schedule-0001",
    *,
    household_id: str = HOUSEHOLD_ID,
) -> PersistedScheduleCreateRequest:
    request = schedule_request(calendar)
    response = build_preparation_schedule(request)
    assert response.unscheduled == []
    return PersistedScheduleCreateRequest.model_validate(
        {
            "calendar_version_id": calendar.id,
            "source_plan_id": None,
            "source_plan_version": None,
            "occurrence_set": {
                "document_version": "preparation-occurrence-set-v1",
                "household_id": household_id,
                "occurrence_set_version": "fixture-occurrences-v1",
                "duration_policy": "conservative_max",
                "occurrences": [
                    {
                        "occurrence_id": "dinner",
                        "recipe_id": "fixture-recipe",
                        "required_finish_minute": 150,
                        "servings": 2.0,
                        "priority": 2,
                    }
                ],
            },
            "profile_versions": {
                "fixture-recipe": (
                    "profile:1/version:v1/sha256:" + PROFILE_HASH
                )
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


def create_calendar(db, version: str = "v1", key: str = "calendar-create-v1"):
    return register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload(version, key),
    )


def create_schedule(
    db,
    calendar,
    key: str = "persisted-schedule-0001",
):
    return create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=persisted_payload(calendar, key),
    )


def test_calendar_registration_is_immutable_idempotent_and_versioned(db):
    first = create_calendar(db)
    retry = create_calendar(db)

    assert retry.id == first.id
    assert retry.content_hash == first.content_hash
    assert retry.active is True
    assert len(retry.resources) == 2
    assert len(retry.content_hash) == 64
    assert retry.resources[0].availability_windows

    with pytest.raises(HTTPException) as exc:
        register_resource_calendar(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=calendar_payload(
                "v1",
                "calendar-create-v1",
                second_window_start=65,
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "calendar_idempotency_conflict"

    all_versions = list_resource_calendars(db, household_id=HOUSEHOLD_ID)
    assert [value.id for value in all_versions] == [first.id]


def test_schedule_creation_persists_complete_replay_provenance(db):
    calendar = create_calendar(db)
    payload = persisted_payload(calendar)
    schedule = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    retry = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=payload,
    )

    assert retry.id == schedule.id
    assert schedule.status == PreparationScheduleStatus.DRAFT
    assert schedule.version == 1
    assert schedule.calendar_content_hash == calendar.content_hash
    assert schedule.occurrence_set is not None
    assert schedule.occurrence_set.household_id == HOUSEHOLD_ID
    assert schedule.occurrence_set_hash == payload.occurrence_set_hash
    assert schedule.schedule_request is not None
    assert len(schedule.schedule_request_hash or "") == 64
    assert schedule.replay_status == "replayable"
    assert len(schedule.schedule_hash) == 64
    assert schedule.schedule.unscheduled == []

    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row is not None
    assert row.occurrence_set_payload == payload.occurrence_set.model_dump(
        mode="json"
    )
    assert row.schedule_request_payload == payload.schedule_request.model_dump(
        mode="json"
    )
    assert len(row.schedule_request_hash or "") == 64

    events = list_schedule_events(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )
    assert len(events) == 1
    assert events[0].event_type == PreparationScheduleEventType.CREATED
    assert events[0].metadata["occurrence_set_hash"] == payload.occurrence_set_hash
    assert events[0].metadata["schedule_hash"] == schedule.schedule_hash


def test_route_household_must_match_occurrence_document(db):
    calendar = create_calendar(db)
    payload = persisted_payload(calendar, household_id="other-home")
    with pytest.raises(HTTPException) as exc:
        create_persisted_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "occurrence_set_household_mismatch"


def test_schedule_rejects_resource_and_replay_forgery(db):
    calendar = create_calendar(db)
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
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
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
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=forged,
        )
    assert exc.value.detail["code"] == "schedule_replay_mismatch"


def test_approval_replays_and_detects_persisted_tampering(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row is not None

    tampered = deepcopy(row.schedule_request_payload)
    tampered["tasks"][0]["duration_minutes"] = 16
    row.schedule_request_payload = tampered
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=transition_payload(
                1,
                "approve-tampered-schedule",
                "Attempt to approve tampered schedule",
            ),
        )
    assert exc.value.detail["code"] in {
        "schedule_provenance_validation_failed",
        "schedule_request_hash_mismatch",
    }

    row.schedule_request_payload = schedule.schedule_request.model_dump(
        mode="json"
    )
    db.add(row)
    db.commit()
    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            1,
            "approve-reviewed-schedule",
            "Owner reviewed occurrence evidence and deterministic replay",
        ),
    )
    assert approved.status == PreparationScheduleStatus.APPROVED
    assert approved.version == 2
    assert approved.approved_by_user_id == OWNER_ID


def test_legacy_retry_backfills_provenance_before_approval(db):
    calendar = create_calendar(db)
    payload = persisted_payload(calendar)
    schedule = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row is not None
    row.occurrence_set_payload = None
    row.schedule_request_payload = None
    row.schedule_request_hash = None
    db.add(row)
    db.commit()

    legacy = get_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )
    assert legacy.replay_status == "legacy_request_missing"

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=transition_payload(
                1,
                "approve-legacy-without-replay",
                "Legacy schedule must fail closed",
            ),
        )
    assert exc.value.detail["code"] == "schedule_replay_input_missing"

    backfilled = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    assert backfilled.id == schedule.id
    assert backfilled.replay_status == "replayable"
    assert backfilled.occurrence_set is not None
    assert backfilled.schedule_request is not None


def test_transitions_are_optimistic_idempotent_and_terminal(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    approval = transition_payload(
        1,
        "approve-schedule-0001",
        "Owner reviewed the calendar and preparation sequence",
    )
    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=approval,
    )
    retry = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=approval,
    )
    assert approved.version == 2
    assert retry.version == 2

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=OWNER_ID,
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
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=OWNER_ID,
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
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.CANCELLED,
            payload=transition_payload(
                3,
                "cancel-completed-schedule",
                "Terminal schedule cannot be cancelled",
            ),
        )
    assert exc.value.detail["code"] == "invalid_schedule_transition"


def test_successor_calendar_invalidates_draft_and_approved_schedules(db):
    first = create_calendar(db)
    draft = create_schedule(db, first, "draft-schedule-v1")
    approved = create_schedule(db, first, "approved-schedule-v1")
    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            approved.version,
            "approve-before-calendar-change",
            "Approve before calendar replacement",
        ),
    )

    second = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload(
            "v2",
            "calendar-create-v2",
            second_window_start=65,
        ),
    )
    assert second.active is True
    assert second.supersedes_calendar_id == first.id

    refreshed_draft = get_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
    )
    refreshed_approved = get_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    assert refreshed_draft.status == PreparationScheduleStatus.INVALIDATED
    assert refreshed_approved.status == PreparationScheduleStatus.INVALIDATED
    assert refreshed_draft.version == 2
    assert refreshed_approved.version == 3
    assert "superseded" in (refreshed_draft.invalidation_reason or "").lower()
