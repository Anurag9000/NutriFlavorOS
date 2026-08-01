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
    ResourceCalendarVersionCreate,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.services.preparation_operations_integrity_service import (
    create_persisted_schedule,
    get_persisted_schedule,
    transition_schedule,
    validate_persisted_schedule_integrity,
)
from backend.services.preparation_operations_service import register_resource_calendar


PROFILE_HASH = "a" * 64
HOUSEHOLD_ID = "replay-home"
USER_ID = "owner@example.test"


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
        id=USER_ID,
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
        name="Replay home",
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
    *,
    reviewed_at: str = "2026-08-01T00:00:00Z",
    idempotency_key: str = "replay-calendar-v1",
) -> ResourceCalendarVersionCreate:
    return ResourceCalendarVersionCreate.model_validate(
        {
            "calendar_version": "v1",
            "horizon_minutes": 120,
            "timezone": "UTC",
            "resources": [
                {
                    "resource_id": "person",
                    "label": "Available cook",
                    "capacity": 1,
                    "resource_kind": "person",
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 120}
                    ],
                    "metadata": {"scope": "test"},
                }
            ],
            "evidence_status": CalendarEvidenceStatus.REVIEWED.value,
            "reviewed_at": reviewed_at,
            "reviewed_by": "Calendar reviewer",
            "notes": "Replay fixture",
            "activate": True,
            "idempotency_key": idempotency_key,
        }
    )


def create_request(calendar) -> PersistedScheduleCreateRequest:
    request = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": calendar.horizon_minutes,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": resource.resource_id,
                    "label": resource.label,
                    "capacity": resource.capacity,
                    "availability_windows": [
                        window.model_dump(mode="json")
                        for window in resource.availability_windows
                    ],
                }
                for resource in calendar.resources
            ],
            "tasks": [
                {
                    "task_id": "dinner.prepare",
                    "duration_minutes": 20,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 60,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {
                        "occurrence_id": "dinner",
                        "recipe_id": "recipe-a",
                        "servings": 2.0,
                        "profile_id": 1,
                        "profile_version": "v1",
                        "profile_content_hash": PROFILE_HASH,
                        "duration_min_minutes": 20,
                        "duration_max_minutes": 20,
                        "duration_policy": "conservative_max",
                        "template_id": "prepare",
                        "active_work": True,
                        "unattended_allowed": False,
                    },
                }
            ],
        }
    )
    response = build_preparation_schedule(request)
    return PersistedScheduleCreateRequest.model_validate(
        {
            "calendar_version_id": calendar.id,
            "occurrence_set": {
                "document_version": "preparation-occurrence-set-v1",
                "household_id": HOUSEHOLD_ID,
                "occurrence_set_version": "occurrences-v1",
                "duration_policy": "conservative_max",
                "occurrences": [
                    {
                        "occurrence_id": "dinner",
                        "recipe_id": "recipe-a",
                        "required_finish_minute": 60,
                        "servings": 2.0,
                        "priority": 1,
                    }
                ],
            },
            "profile_versions": {
                "recipe-a": f"profile:1/version:v1/sha256:{PROFILE_HASH}"
            },
            "schedule_request": request.model_dump(mode="json"),
            "schedule_response": response.model_dump(mode="json"),
            "idempotency_key": "replay-schedule-v1",
        }
    )


def approval(version: int = 1) -> ScheduleStateTransitionRequest:
    return ScheduleStateTransitionRequest.model_validate(
        {
            "expected_version": version,
            "reason": "Owner reviewed the replayable schedule",
            "idempotency_key": "replay-approval-v1",
            "metadata": {"test": True},
        }
    )


def register_calendar(db):
    return register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=USER_ID,
        payload=calendar_payload(),
    )


def create_schedule(db):
    calendar = register_calendar(db)
    payload = create_request(calendar)
    schedule = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=USER_ID,
        payload=payload,
    )
    return calendar, payload, schedule


def test_compatibility_facade_persists_and_replays_current_contract(db):
    _, payload, schedule = create_schedule(db)
    assert schedule.replay_status == "replayable"
    assert schedule.occurrence_set is not None
    assert schedule.schedule_request is not None
    assert len(schedule.schedule_request_hash or "") == 64

    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row is not None
    request, replay = validate_persisted_schedule_integrity(db, row)
    assert request.model_dump(mode="json") == payload.schedule_request.model_dump(
        mode="json"
    )
    assert replay.model_dump(mode="json") == payload.schedule_response.model_dump(
        mode="json"
    )

    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        actor_user_id=USER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=approval(),
    )
    assert approved.status.value == "approved"
    assert approved.replay_status == "replayable"


def test_approval_detects_request_response_and_combined_hash_tampering(db):
    _, payload, schedule = create_schedule(db)
    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row is not None

    tampered_request = deepcopy(row.schedule_request_payload)
    tampered_request["tasks"][0]["earliest_start_minute"] = 5
    row.schedule_request_payload = tampered_request
    db.add(row)
    db.commit()
    db.expire_all()
    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=USER_ID,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=approval(),
        )
    assert exc.value.detail["code"] == "schedule_request_hash_mismatch"

    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row is not None
    row.schedule_request_payload = payload.schedule_request.model_dump(mode="json")
    tampered_response = deepcopy(row.schedule_payload)
    tampered_response["scheduled"][0]["start_minute"] = 5
    tampered_response["scheduled"][0]["finish_minute"] = 25
    row.schedule_payload = tampered_response
    db.add(row)
    db.commit()
    db.expire_all()
    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=USER_ID,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=approval(),
        )
    assert exc.value.detail["code"] == "schedule_approval_replay_mismatch"

    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row is not None
    row.schedule_payload = payload.schedule_response.model_dump(mode="json")
    row.schedule_hash = "f" * 64
    db.add(row)
    db.commit()
    db.expire_all()
    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=USER_ID,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=approval(),
        )
    assert exc.value.detail["code"] == "schedule_hash_mismatch"


def test_legacy_row_is_readable_nonapprovable_and_exact_retry_backfills(db):
    _, payload, schedule = create_schedule(db)
    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row is not None
    row.occurrence_set_payload = None
    row.schedule_request_payload = None
    row.schedule_request_hash = None
    db.add(row)
    db.commit()

    view = get_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )
    assert view.replay_status == "legacy_request_missing"
    assert view.schedule_request is None

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            actor_user_id=USER_ID,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=approval(),
        )
    assert exc.value.detail["code"] == "schedule_replay_input_missing"

    backfilled = create_persisted_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=USER_ID,
        payload=payload,
    )
    assert backfilled.id == schedule.id
    assert backfilled.replay_status == "replayable"
    assert backfilled.occurrence_set is not None
    assert backfilled.schedule_request is not None


def test_timezone_equivalent_review_timestamps_hash_and_retry_identically(db):
    first_payload = calendar_payload(reviewed_at="2026-08-01T00:00:00Z")
    offset_payload = calendar_payload(reviewed_at="2026-08-01T05:30:00+05:30")
    assert first_payload.reviewed_at == "2026-08-01T00:00:00Z"
    assert offset_payload.reviewed_at == first_payload.reviewed_at

    first = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=USER_ID,
        payload=first_payload,
    )
    retry = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=USER_ID,
        payload=offset_payload,
    )
    assert retry.id == first.id
    assert retry.content_hash == first.content_hash
