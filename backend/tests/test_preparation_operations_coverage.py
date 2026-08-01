from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import preparation_operations_routes
from backend.database import Base, DBHousehold, DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.services.preparation_operations_coverage_service import (
    get_preparation_operations_coverage,
)
from backend.utils.security import get_current_user


HOUSEHOLD_ID = "coverage-home"
OWNER_ID = "coverage-owner@example.test"
NOW = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        db.add(
            DBUser(
                id=OWNER_ID,
                name="Coverage owner",
                liked_ingredients=[],
                disliked_ingredients=[],
                allergies=[],
                dietary_restrictions=[],
                health_conditions=[],
                medications=[],
            )
        )
        db.add(
            DBHousehold(
                id=HOUSEHOLD_ID,
                owner_user_id=OWNER_ID,
                name="Coverage household",
                timezone="UTC",
                version=1,
            )
        )
        db.commit()
    return Session


def _seed_calendar_and_schedules(Session) -> None:
    with Session() as db:
        calendar = DBResourceCalendarVersion(
            household_id=HOUSEHOLD_ID,
            calendar_version="reviewed-v1",
            horizon_minutes=180,
            timezone="UTC",
            evidence_status="reviewed",
            reviewed_at=NOW,
            reviewed_by="Coverage reviewer",
            notes=None,
            content_hash="a" * 64,
            supersedes_calendar_id=None,
            active=True,
            created_by_user_id=OWNER_ID,
            idempotency_key="coverage-calendar-v1",
            request_fingerprint="b" * 64,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(calendar)
        db.flush()

        replayable = DBPersistedPreparationSchedule(
            household_id=HOUSEHOLD_ID,
            calendar_version_id=calendar.id,
            calendar_content_hash=calendar.content_hash,
            source_plan_id=None,
            source_plan_version=None,
            occurrence_set_version="occurrences-v1",
            occurrence_set_hash="c" * 64,
            occurrence_set_payload={"document_version": "fixture"},
            profile_versions={},
            schedule_request_payload={"horizon_minutes": 180},
            schedule_request_hash="d" * 64,
            schedule_payload={"method": "fixture"},
            schedule_hash="e" * 64,
            status="draft",
            version=1,
            notes=None,
            created_by_user_id=OWNER_ID,
            approved_by_user_id=None,
            approved_at=None,
            invalidated_at=None,
            invalidation_reason=None,
            creation_idempotency_key="coverage-schedule-replayable",
            creation_request_fingerprint="f" * 64,
            created_at=NOW,
            updated_at=NOW,
        )
        legacy = DBPersistedPreparationSchedule(
            household_id=HOUSEHOLD_ID,
            calendar_version_id=calendar.id,
            calendar_content_hash=calendar.content_hash,
            source_plan_id=None,
            source_plan_version=None,
            occurrence_set_version="occurrences-legacy",
            occurrence_set_hash="1" * 64,
            occurrence_set_payload=None,
            profile_versions={},
            schedule_request_payload={"horizon_minutes": 180},
            schedule_request_hash="2" * 64,
            schedule_payload={"method": "fixture"},
            schedule_hash="3" * 64,
            status="cancelled",
            version=2,
            notes=None,
            created_by_user_id=OWNER_ID,
            approved_by_user_id=None,
            approved_at=None,
            invalidated_at=None,
            invalidation_reason=None,
            creation_idempotency_key="coverage-schedule-legacy",
            creation_request_fingerprint="4" * 64,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add_all([replayable, legacy])
        db.flush()
        db.add_all(
            [
                DBPreparationScheduleEvent(
                    schedule_id=replayable.id,
                    household_id=HOUSEHOLD_ID,
                    event_type="created",
                    actor_user_id=OWNER_ID,
                    from_status=None,
                    to_status="draft",
                    reason="Created replayable schedule",
                    event_metadata={},
                    idempotency_key="coverage-event-replayable",
                    request_fingerprint="5" * 64,
                    created_at=NOW,
                ),
                DBPreparationScheduleEvent(
                    schedule_id=legacy.id,
                    household_id=HOUSEHOLD_ID,
                    event_type="created",
                    actor_user_id=OWNER_ID,
                    from_status=None,
                    to_status="draft",
                    reason="Created legacy schedule",
                    event_metadata={},
                    idempotency_key="coverage-event-legacy-created",
                    request_fingerprint="6" * 64,
                    created_at=NOW,
                ),
                DBPreparationScheduleEvent(
                    schedule_id=legacy.id,
                    household_id=HOUSEHOLD_ID,
                    event_type="cancelled",
                    actor_user_id=OWNER_ID,
                    from_status="draft",
                    to_status="cancelled",
                    reason="Cancelled legacy schedule",
                    event_metadata={},
                    idempotency_key="coverage-event-legacy-cancelled",
                    request_fingerprint="7" * 64,
                    created_at=NOW,
                ),
            ]
        )
        db.commit()


def test_empty_household_coverage_is_explicit(session_factory):
    with session_factory() as db:
        coverage = get_preparation_operations_coverage(
            db,
            household_id=HOUSEHOLD_ID,
        )

    assert coverage.calendar_total == 0
    assert coverage.schedule_total == 0
    assert coverage.event_total == 0
    assert coverage.occurrence_document_coverage == 0.0
    assert coverage.scheduler_request_coverage == 0.0
    assert coverage.replayable_schedule_coverage == 0.0
    assert coverage.schedule_status_counts == {
        "draft": 0,
        "approved": 0,
        "invalidated": 0,
        "completed": 0,
        "cancelled": 0,
    }
    assert "No active reviewed resource calendar" in coverage.warnings[0]
    assert any("No persisted" in value for value in coverage.warnings)


def test_coverage_distinguishes_complete_and_legacy_provenance(session_factory):
    _seed_calendar_and_schedules(session_factory)
    with session_factory() as db:
        coverage = get_preparation_operations_coverage(
            db,
            household_id=HOUSEHOLD_ID,
        )

    assert coverage.calendar_total == 1
    assert coverage.reviewed_calendar_total == 1
    assert coverage.active_reviewed_calendar_count == 1
    assert coverage.schedule_total == 2
    assert coverage.schedule_status_counts["draft"] == 1
    assert coverage.schedule_status_counts["cancelled"] == 1
    assert coverage.replay_status_counts == {
        "replayable": 1,
        "legacy_request_missing": 0,
        "legacy_occurrence_set_missing": 1,
    }
    assert coverage.occurrence_document_count == 1
    assert coverage.scheduler_request_count == 2
    assert coverage.replayable_schedule_count == 1
    assert coverage.replayable_draft_count == 1
    assert coverage.source_plan_linked_count == 0
    assert coverage.event_total == 3
    assert coverage.occurrence_document_coverage == 0.5
    assert coverage.scheduler_request_coverage == 1.0
    assert coverage.replayable_schedule_coverage == 0.5
    assert any("legacy schedules" in value for value in coverage.warnings)
    assert any("source plan" in value for value in coverage.warnings)


def test_viewer_authorized_coverage_route_and_outsider_non_disclosure(
    session_factory,
    monkeypatch,
):
    _seed_calendar_and_schedules(session_factory)
    identity = {"user_id": OWNER_ID}

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def current_user():
        return SimpleNamespace(id=identity["user_id"])

    def access(db, household_id, user_id, minimum_role):
        if household_id != HOUSEHOLD_ID or user_id != OWNER_ID:
            raise HTTPException(status_code=404, detail="Resource not found")
        assert minimum_role == HouseholdRole.VIEWER
        return db.get(DBHousehold, HOUSEHOLD_ID), SimpleNamespace(
            role=HouseholdRole.OWNER
        )

    monkeypatch.setattr(
        preparation_operations_routes,
        "require_household_access",
        access,
    )
    app = FastAPI()
    app.include_router(preparation_operations_routes.router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = current_user
    client = TestClient(app)

    response = client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/coverage"
    )
    assert response.status_code == 200
    assert response.json()["replayable_schedule_coverage"] == 0.5
    assert response.json()["event_total"] == 3

    identity["user_id"] = "outsider@example.test"
    denied = client.get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/coverage"
    )
    assert denied.status_code == 404
