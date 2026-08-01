#!/usr/bin/env python3
"""PostgreSQL concurrency probe for persisted preparation operations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Callable

from backend.database import DBHousehold, DBUser, SessionLocal
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
    DBHouseholdPreparationResource,
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.services.preparation_operations_integrity_service import (
    create_persisted_schedule,
    transition_schedule,
)
from backend.services.preparation_operations_service import register_resource_calendar


USER_ID = "ci-preparation-operations@example.test"
HOUSEHOLD_ID = "ci-preparation-operations-home"


def _run_pair(left: Callable[[], object], right: Callable[[], object]):
    barrier = Barrier(2)

    def execute(label: str, callback: Callable[[], object]):
        barrier.wait(timeout=10)
        try:
            return label, callback()
        except Exception as exc:
            return label, exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(execute, "left", left),
            pool.submit(execute, "right", right),
        ]
        return [future.result(timeout=45) for future in futures]


def _reset() -> None:
    with SessionLocal() as db:
        db.query(DBPreparationScheduleEvent).filter(
            DBPreparationScheduleEvent.household_id == HOUSEHOLD_ID
        ).delete(synchronize_session=False)
        db.query(DBPersistedPreparationSchedule).filter(
            DBPersistedPreparationSchedule.household_id == HOUSEHOLD_ID
        ).delete(synchronize_session=False)
        calendar_ids = [
            value[0]
            for value in db.query(DBResourceCalendarVersion.id)
            .filter(DBResourceCalendarVersion.household_id == HOUSEHOLD_ID)
            .all()
        ]
        if calendar_ids:
            db.query(DBHouseholdPreparationResource).filter(
                DBHouseholdPreparationResource.calendar_version_id.in_(calendar_ids)
            ).delete(synchronize_session=False)
        db.query(DBResourceCalendarVersion).filter(
            DBResourceCalendarVersion.household_id == HOUSEHOLD_ID
        ).delete(synchronize_session=False)
        db.query(DBHousehold).filter(DBHousehold.id == HOUSEHOLD_ID).delete(
            synchronize_session=False
        )
        db.query(DBUser).filter(DBUser.id == USER_ID).delete(
            synchronize_session=False
        )
        db.commit()


def _seed() -> None:
    with SessionLocal() as db:
        user = DBUser(
            id=USER_ID,
            name="CI preparation operations",
            liked_ingredients=[],
            disliked_ingredients=[],
            allergies=[],
            dietary_restrictions=[],
            health_conditions=[],
            medications=[],
        )
        household = DBHousehold(
            id=HOUSEHOLD_ID,
            owner_user_id=USER_ID,
            name="CI preparation operations",
            timezone="UTC",
            version=1,
        )
        db.add_all([user, household])
        db.commit()


def _calendar(version: str, key: str, *, second_start: int = 60):
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
                        {"start_minute": second_start, "end_minute": 150},
                    ],
                    "metadata": {"probe": "postgresql"},
                },
                {
                    "resource_id": "burner",
                    "label": "Burner",
                    "capacity": 1,
                    "resource_kind": "equipment",
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 150}
                    ],
                    "metadata": {"probe": "postgresql"},
                },
            ],
            "evidence_status": CalendarEvidenceStatus.REVIEWED.value,
            "reviewed_at": "2026-08-01T00:00:00Z",
            "reviewed_by": "CI preparation operations",
            "activate": True,
            "idempotency_key": key,
        }
    )


def _register(payload):
    with SessionLocal() as db:
        return register_resource_calendar(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=USER_ID,
            payload=payload,
        )


def _schedule_payload(calendar, key: str):
    request = PreparationScheduleRequest.model_validate(
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
    response = build_preparation_schedule(request)
    return PersistedScheduleCreateRequest.model_validate(
        {
            "calendar_version_id": calendar.id,
            "occurrence_set_version": "ci-occurrences-v1",
            "occurrence_set_hash": "b" * 64,
            "profile_versions": {
                "ci-recipe": "profile:1/version:1/sha256:" + "a" * 64
            },
            "schedule_request": request.model_dump(mode="json"),
            "schedule_response": response.model_dump(mode="json"),
            "idempotency_key": key,
        }
    )


def _create_schedule(payload):
    with SessionLocal() as db:
        return create_persisted_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=USER_ID,
            payload=payload,
        )


def _transition(schedule_id: int, event_type: PreparationScheduleEventType, key: str):
    with SessionLocal() as db:
        return transition_schedule(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule_id,
            actor_user_id=USER_ID,
            event_type=event_type,
            payload=ScheduleStateTransitionRequest.model_validate(
                {
                    "expected_version": 1,
                    "reason": f"CI concurrent {event_type.value}",
                    "idempotency_key": key,
                    "metadata": {"probe": "postgresql"},
                }
            ),
        )


def _assert_identical_calendar_retry_collapses() -> None:
    payload = _calendar("calendar-v1", "ci-calendar-identical")
    results = _run_pair(lambda: _register(payload), lambda: _register(payload))
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    ids = {value.id for _, value in results}
    assert len(ids) == 1
    with SessionLocal() as db:
        rows = db.query(DBResourceCalendarVersion).filter(
            DBResourceCalendarVersion.household_id == HOUSEHOLD_ID
        ).all()
        assert len(rows) == 1
        assert rows[0].active is True


def _assert_identical_schedule_retry_collapses() -> tuple[object, object]:
    calendar = _register(_calendar("calendar-v1", "ci-calendar-schedule"))
    payload = _schedule_payload(calendar, "ci-schedule-identical")
    results = _run_pair(
        lambda: _create_schedule(payload),
        lambda: _create_schedule(payload),
    )
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    ids = {value.id for _, value in results}
    assert len(ids) == 1
    schedule = next(value for _, value in results)
    with SessionLocal() as db:
        rows = db.query(DBPersistedPreparationSchedule).filter(
            DBPersistedPreparationSchedule.household_id == HOUSEHOLD_ID
        ).all()
        events = db.query(DBPreparationScheduleEvent).filter(
            DBPreparationScheduleEvent.household_id == HOUSEHOLD_ID
        ).all()
        assert len(rows) == 1
        assert len(events) == 1
        assert rows[0].schedule_request_hash is not None
    return calendar, schedule


def _assert_competing_transitions_have_one_winner() -> None:
    calendar = _register(_calendar("calendar-v1", "ci-calendar-transition"))
    schedule = _create_schedule(
        _schedule_payload(calendar, "ci-schedule-transition")
    )
    results = _run_pair(
        lambda: _transition(
            schedule.id,
            PreparationScheduleEventType.APPROVED,
            "ci-transition-approve",
        ),
        lambda: _transition(
            schedule.id,
            PreparationScheduleEventType.CANCELLED,
            "ci-transition-cancel",
        ),
    )
    successes = [value for _, value in results if not isinstance(value, Exception)]
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert len(successes) == 1, results
    assert len(errors) == 1, results
    with SessionLocal() as db:
        row = db.get(DBPersistedPreparationSchedule, schedule.id)
        assert row.status in {
            PreparationScheduleStatus.APPROVED.value,
            PreparationScheduleStatus.CANCELLED.value,
        }
        assert row.version == 2
        events = db.query(DBPreparationScheduleEvent).filter(
            DBPreparationScheduleEvent.schedule_id == schedule.id
        ).all()
        assert len(events) == 2


def _assert_supersession_racing_approval_always_invalidates() -> None:
    first = _register(_calendar("calendar-v1", "ci-calendar-race-v1"))
    schedule = _create_schedule(
        _schedule_payload(first, "ci-schedule-calendar-race")
    )
    second_payload = _calendar(
        "calendar-v2",
        "ci-calendar-race-v2",
        second_start=70,
    )
    results = _run_pair(
        lambda: _transition(
            schedule.id,
            PreparationScheduleEventType.APPROVED,
            "ci-calendar-race-approval",
        ),
        lambda: _register(second_payload),
    )
    successes = [value for _, value in results if not isinstance(value, Exception)]
    assert len(successes) >= 1, results
    with SessionLocal() as db:
        row = db.get(DBPersistedPreparationSchedule, schedule.id)
        active = db.query(DBResourceCalendarVersion).filter(
            DBResourceCalendarVersion.household_id == HOUSEHOLD_ID,
            DBResourceCalendarVersion.active.is_(True),
        ).one()
        assert active.calendar_version == "calendar-v2"
        assert row.status == PreparationScheduleStatus.INVALIDATED.value
        events = (
            db.query(DBPreparationScheduleEvent)
            .filter(DBPreparationScheduleEvent.schedule_id == schedule.id)
            .order_by(DBPreparationScheduleEvent.id)
            .all()
        )
        assert events[-1].event_type == PreparationScheduleEventType.INVALIDATED.value
        assert events[-1].event_metadata["replacement_calendar_id"] == active.id


def main() -> int:
    _reset()
    _seed()
    try:
        _assert_identical_calendar_retry_collapses()
        _reset()
        _seed()
        _assert_identical_schedule_retry_collapses()
        _reset()
        _seed()
        _assert_competing_transitions_have_one_winner()
        _reset()
        _seed()
        _assert_supersession_racing_approval_always_invalidates()
        print("Preparation operations PostgreSQL concurrency probe passed")
        return 0
    finally:
        _reset()


if __name__ == "__main__":
    raise SystemExit(main())
