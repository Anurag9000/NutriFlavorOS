"""Block task execution on a source schedule after repair acceptance.

Repair acceptance creates a replacement draft while preserving the source record
as immutable history. Once that boundary is crossed, the source must not begin a
second execution history. This guard shares the household lock with acceptance so
concurrent acceptance and task-start attempts serialize to one authoritative result.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionMutationView,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_operations_service import _lock_household
from backend.services.preparation_task_execution_authoritative_service import (
    record_task_execution_event as _record_task_execution_event,
)


def record_task_execution_event_with_replacement_guard(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    task_id: str,
    actor_user_id: str,
    event_type: PreparationTaskExecutionEventType,
    payload: PreparationTaskExecutionEventCreate,
) -> PreparationTaskExecutionMutationView:
    """Record a task event only when the schedule is not an accepted source."""

    _lock_household(db, household_id)
    schedule = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    replacement = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.household_id == household_id,
            DBPreparationRepairProposalAcceptance.source_schedule_id == schedule.id,
        )
        .with_for_update()
        .first()
    )
    if replacement is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_schedule_has_accepted_replacement",
                "message": (
                    "Task execution is blocked because this source schedule has "
                    "an accepted repaired replacement"
                ),
                "source_schedule_id": schedule.id,
                "source_schedule_version_at_acceptance": (
                    replacement.source_schedule_version
                ),
                "accepted_proposal_id": replacement.proposal_id,
                "acceptance_id": replacement.id,
                "replacement_schedule_id": replacement.created_schedule_id,
            },
        )

    return _record_task_execution_event(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        task_id=task_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload=payload,
    )


__all__ = ["record_task_execution_event_with_replacement_guard"]
