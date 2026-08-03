from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.database import DBUser
from backend.services.preparation_schedule_support_export_authorized_service import (
    export_authorized_preparation_schedule_support_snapshot,
)
from backend.services.preparation_schedule_support_export_service import (
    export_preparation_schedule_support_snapshot,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    db,
)


def test_authorized_support_snapshot_revalidates_owner_access(db):
    calendar = create_calendar(
        db,
        version="support-auth-owner-v1",
        key="support-auth-owner-calendar-v1",
    )
    schedule = create_schedule(
        db,
        calendar,
        key="support-auth-owner-schedule-v1",
    )

    exported = export_authorized_preparation_schedule_support_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
        authorized_user_id=OWNER_ID,
    )

    assert exported.household_id == HOUSEHOLD_ID
    assert exported.schedule_id == schedule.id
    assert exported.snapshot_read_only is True
    assert exported.mutation_performed is False


def test_authorized_support_snapshot_fails_closed_for_nonmember(db):
    calendar = create_calendar(
        db,
        version="support-auth-outsider-v1",
        key="support-auth-outsider-calendar-v1",
    )
    schedule = create_schedule(
        db,
        calendar,
        key="support-auth-outsider-schedule-v1",
    )
    outsider_id = "snapshot-outsider@example.test"
    db.add(
        DBUser(
            id=outsider_id,
            name="Snapshot outsider",
            liked_ingredients=[],
            disliked_ingredients=[],
            allergies=[],
            dietary_restrictions=[],
            health_conditions=[],
            medications=[],
        )
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        export_authorized_preparation_schedule_support_snapshot(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule.id,
            authorized_user_id=outsider_id,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Resource not found"


def test_operator_snapshot_remains_explicitly_separate_from_http_authorization(db):
    calendar = create_calendar(
        db,
        version="support-auth-operator-v1",
        key="support-auth-operator-calendar-v1",
    )
    schedule = create_schedule(
        db,
        calendar,
        key="support-auth-operator-schedule-v1",
    )

    exported = export_preparation_schedule_support_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )

    assert exported.schedule_id == schedule.id
    assert exported.database_dialect == "sqlite"
    assert exported.snapshot_isolation == "serializable"
