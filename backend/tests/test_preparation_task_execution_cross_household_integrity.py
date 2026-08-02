from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.database import DBHousehold
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
)
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_operations_coverage_service import (
    get_preparation_operations_coverage,
)
from backend.services.preparation_task_execution_authoritative_service import (
    get_task_execution_overview,
)
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from backend.tests.test_preparation_task_execution_authoritative_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    approved_schedule,
    db,
    event_payload,
)


OTHER_HOUSEHOLD_ID = "authoritative-other-home"


def test_cross_household_event_link_is_rejected_by_overview_and_coverage(db):
    db.add(
        DBHousehold(
            id=OTHER_HOUSEHOLD_ID,
            owner_user_id=OWNER_ID,
            name="Other authoritative home",
            timezone="UTC",
            version=1,
        )
    )
    db.commit()
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
            "cross-household-start",
        ),
    )
    row = db.get(DBPreparationTaskExecutionEvent, started.event.id)
    row.household_id = OTHER_HOUSEHOLD_ID
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_task_execution_overview(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
        )
    assert exc.value.detail["code"] == "execution_event_household_mismatch"
    assert exc.value.detail["event_ids"] == [started.event.id]

    coverage = get_preparation_operations_coverage(
        db,
        household_id=HOUSEHOLD_ID,
    )
    assert coverage.execution_scope_schedule_count == 1
    assert coverage.execution_invalid_schedule_count == 1
    assert coverage.deterministic_task_count == 0
    assert any("structurally invalid" in value for value in coverage.warnings)
