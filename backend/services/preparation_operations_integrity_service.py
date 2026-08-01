"""Compatibility facade for replay-aware preparation operations.

The authoritative implementation now lives in
``backend.services.preparation_operations_service``. This module remains only
for stable imports used by older callers; it does not maintain a second mutation
path or duplicate persistence logic.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBResourceCalendarVersion,
)
from backend.services import preparation_operations_service as base


create_persisted_schedule = base.create_persisted_schedule
get_persisted_schedule = base.get_persisted_schedule
list_persisted_schedules = base.list_persisted_schedules
transition_schedule = base.transition_schedule


def validate_persisted_schedule_integrity(
    db: Session,
    row: DBPersistedPreparationSchedule,
) -> tuple[PreparationScheduleRequest, PreparationScheduleResponse]:
    """Validate and replay one persisted schedule without mutating its state."""

    calendar = db.get(DBResourceCalendarVersion, row.calendar_version_id)
    if calendar is None or calendar.household_id != row.household_id:
        raise base.HTTPException(
            status_code=409,
            detail={
                "code": "schedule_calendar_missing",
                "message": (
                    "The immutable resource calendar linked to this schedule "
                    "is unavailable"
                ),
            },
        )
    base._validate_approval_replay(
        db,
        household_id=row.household_id,
        schedule=row,
        calendar=calendar,
    )
    _, request, response, replay_status = base._parse_persisted_provenance(row)
    if request is None or replay_status != "replayable":
        raise base.HTTPException(
            status_code=409,
            detail={
                "code": "schedule_replay_input_missing",
                "message": "Persisted schedule is not fully replayable",
            },
        )
    return request, response
