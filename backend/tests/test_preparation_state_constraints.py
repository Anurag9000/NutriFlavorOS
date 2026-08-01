from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBHousehold, DBUser
from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    ResourceCalendarVersionCreate,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.services.preparation_operations_integrity_service import (
    create_persisted_schedule,
)
from backend.services.preparation_operations_service import register_resource_calendar


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
    user = DBUser(
        id="constraint-owner@example.test",
        name="Constraint owner",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    household = DBHousehold(
        id="constraint-home",
        owner_user_id=user.id,
        name="Constraint home",
        timezone="UTC",
        version=1,
    )
    session.add_all([user, household])
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _calendar(db):
    return register_resource_calendar(
        db,
        household_id="constraint-home",
        actor_user_id="constraint-owner@example.test",
        payload=ResourceCalendarVersionCreate.model_validate(
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
                        "metadata": {},
                    }
                ],
                "evidence_status": CalendarEvidenceStatus.REVIEWED.value,
                "reviewed_at": "2026-08-01T00:00:00Z",
                "reviewed_by": "Constraint reviewer",
                "activate": True,
                "idempotency_key": "constraint-calendar-v1",
            }
        ),
    )


def _schedule(db, calendar):
    request = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 120,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "person",
                    "label": "Available cook",
                    "capacity": 1,
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 120}
                    ],
                }
            ],
            "tasks": [
                {
                    "task_id": "prep",
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
    return create_persisted_schedule(
        db,
        household_id="constraint-home",
        actor_user_id="constraint-owner@example.test",
        payload=PersistedScheduleCreateRequest.model_validate(
            {
                "calendar_version_id": calendar.id,
                "occurrence_set_version": "v1",
                "occurrence_set_hash": "b" * 64,
                "profile_versions": {
                    "recipe": "profile:1/version:1/sha256:" + "a" * 64
                },
                "schedule_request": request.model_dump(mode="json"),
                "schedule_response": response.model_dump(mode="json"),
                "idempotency_key": "constraint-schedule-v1",
            }
        ),
    )


def test_active_draft_calendar_is_rejected(db):
    now = datetime.now(timezone.utc)
    db.add(
        DBResourceCalendarVersion(
            household_id="constraint-home",
            calendar_version="invalid-draft",
            horizon_minutes=120,
            timezone="UTC",
            evidence_status="draft",
            reviewed_at=None,
            reviewed_by=None,
            notes=None,
            content_hash="a" * 64,
            supersedes_calendar_id=None,
            active=True,
            created_by_user_id="constraint-owner@example.test",
            idempotency_key="invalid-active-draft",
            request_fingerprint="b" * 64,
            created_at=now,
            updated_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_schedule_status_requires_consistent_approval_and_invalidation_fields(db):
    calendar = _calendar(db)
    schedule = _schedule(db, calendar)
    row = db.get(DBPersistedPreparationSchedule, schedule.id)

    row.status = "approved"
    row.version = 2
    db.add(row)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    row = db.get(DBPersistedPreparationSchedule, schedule.id)
    row.status = "invalidated"
    row.version = 2
    db.add(row)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_event_action_must_match_status_pair_and_reason(db):
    calendar = _calendar(db)
    schedule = _schedule(db, calendar)
    now = datetime.now(timezone.utc)
    db.add(
        DBPreparationScheduleEvent(
            schedule_id=schedule.id,
            household_id="constraint-home",
            event_type="approved",
            actor_user_id="constraint-owner@example.test",
            from_status="approved",
            to_status="approved",
            reason="invalid transition pair",
            event_metadata={},
            idempotency_key="invalid-event-pair",
            request_fingerprint="c" * 64,
            created_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(
        DBPreparationScheduleEvent(
            schedule_id=schedule.id,
            household_id="constraint-home",
            event_type="cancelled",
            actor_user_id="constraint-owner@example.test",
            from_status="draft",
            to_status="cancelled",
            reason="   ",
            event_metadata={},
            idempotency_key="invalid-event-reason",
            request_fingerprint="d" * 64,
            created_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
