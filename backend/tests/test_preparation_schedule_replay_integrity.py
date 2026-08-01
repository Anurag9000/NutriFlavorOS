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
)
from backend.services.preparation_operations_service import (
    create_persisted_schedule as create_legacy_schedule,
    register_resource_calendar,
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
        id="replay-home",
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
                    "task_id": "prepare",
                    "duration_minutes": 20,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 60,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {"profile_content_hash": "a" * 64},
                }
            ],
        }
    )
    response = build_preparation_schedule(request)
    return PersistedScheduleCreateRequest.model_validate(
        {
            "calendar_version_id": calendar.id,
            "occurrence_set_version": "occurrences-v1",
            "occurrence_set_hash": "b" * 64,
            "profile_versions": {
                "recipe-a": "profile:1/version:1/sha256:" + "a" * 64
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
        household_id="replay-home",
        actor_user_id="owner@example.test",
        payload=calendar_payload(),
    )


def test_new_schedule_persists_request_hash_and_replays_on_approval(db):
    calendar = register_calendar(db)
    payload = create_request(calendar)
    schedule = create_persisted_schedule(
        db,
        household_id="replay-home",
        actor_user_id="owner@example.test",
        payload=payload,
    )
    assert schedule.replay_status == "replayable"
    assert schedule.schedule_request is not None
    assert len(schedule.schedule_request_hash or "") == 64

    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    assert row.schedule_request_payload == payload.schedule_request.model_dump(mode="json")
    assert row.schedule_request_hash == schedule.schedule_request_hash

    approved = transition_schedule(
        db,
        household_id="replay-home",
        schedule_id=schedule.id,
        actor_user_id="owner@example.test",
        event_type=PreparationScheduleEventType.APPROVED,
        payload=approval(),
    )
    assert approved.status.value == "approved"
    assert approved.replay_status == "replayable"


def test_approval_detects_request_response_and_combined_hash_tampering(db):
    calendar = register_calendar(db)
    payload = create_request(calendar)

    request_tampered = create_persisted_schedule(
        db,
        household_id="replay-home",
        actor_user_id="owner@example.test",
        payload=payload,
    )
    row = db.get(DBPersistedPreparationSchedule, request_tampered.id)
    row.schedule_request_payload["tasks"][0]["duration_minutes"] = 25
    db.add(row)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id="replay-home",
            schedule_id=row.id,
            actor_user_id="owner@example.test",
            event_type=PreparationScheduleEventType.APPROVED,
            payload=approval(),
        )
    assert exc.value.detail["code"] == "schedule_request_hash_mismatch"

    # Restore the request and tamper only with the stored response.
    row.schedule_request_payload = payload.schedule_request.model_dump(mode="json")
    row.schedule_payload["scheduled"][0]["start_minute"] = 5
    row.schedule_payload["scheduled"][0]["finish_minute"] = 25
    db.add(row)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id="replay-home",
            schedule_id=row.id,
            actor_user_id="owner@example.test",
            event_type=PreparationScheduleEventType.APPROVED,
            payload=approval(),
        )
    assert exc.value.detail["code"] == "stored_schedule_replay_mismatch"

    row.schedule_payload = payload.schedule_response.model_dump(mode="json")
    row.schedule_hash = "f" * 64
    db.add(row)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id="replay-home",
            schedule_id=row.id,
            actor_user_id="owner@example.test",
            event_type=PreparationScheduleEventType.APPROVED,
            payload=approval(),
        )
    assert exc.value.detail["code"] == "schedule_hash_mismatch"


def test_legacy_row_is_readable_but_not_approvable_until_exact_retry_backfills(db):
    calendar = register_calendar(db)
    payload = create_request(calendar)
    legacy = create_legacy_schedule(
        db,
        household_id="replay-home",
        actor_user_id="owner@example.test",
        payload=payload,
    )
    view = get_persisted_schedule(
        db,
        household_id="replay-home",
        schedule_id=legacy.id,
    )
    assert view.replay_status == "legacy_request_missing"
    assert view.schedule_request is None

    with pytest.raises(HTTPException) as exc:
        transition_schedule(
            db,
            household_id="replay-home",
            schedule_id=legacy.id,
            actor_user_id="owner@example.test",
            event_type=PreparationScheduleEventType.APPROVED,
            payload=approval(),
        )
    assert exc.value.detail["code"] == "schedule_request_provenance_missing"

    backfilled = create_persisted_schedule(
        db,
        household_id="replay-home",
        actor_user_id="owner@example.test",
        payload=payload,
    )
    assert backfilled.id == legacy.id
    assert backfilled.replay_status == "replayable"
    assert backfilled.schedule_request is not None


def test_timezone_equivalent_review_timestamps_hash_and_retry_identically(db):
    first_payload = calendar_payload(reviewed_at="2026-08-01T00:00:00Z")
    offset_payload = calendar_payload(reviewed_at="2026-08-01T05:30:00+05:30")
    assert first_payload.reviewed_at == "2026-08-01T00:00:00Z"
    assert offset_payload.reviewed_at == first_payload.reviewed_at

    first = register_resource_calendar(
        db,
        household_id="replay-home",
        actor_user_id="owner@example.test",
        payload=first_payload,
    )
    retry = register_resource_calendar(
        db,
        household_id="replay-home",
        actor_user_id="owner@example.test",
        payload=offset_payload,
    )
    assert retry.id == first.id
    assert retry.content_hash == first.content_hash
