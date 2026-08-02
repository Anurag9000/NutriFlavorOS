"""Authoritative read-only task-execution eligibility resolution."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation_task_execution_eligibility import (
    PreparationTaskExecutionEligibilityReason,
    PreparationTaskExecutionEligibilityView,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)


def get_task_execution_eligibility(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> PreparationTaskExecutionEligibilityView:
    schedule = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    task_event_count = (
        db.query(DBPreparationTaskExecutionEvent)
        .filter(
            DBPreparationTaskExecutionEvent.household_id == household_id,
            DBPreparationTaskExecutionEvent.schedule_id == schedule.id,
        )
        .count()
    )
    replacement = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.household_id == household_id,
            DBPreparationRepairProposalAcceptance.source_schedule_id == schedule.id,
        )
        .first()
    )
    if replacement is not None:
        replacement_schedule = db.get(
            DBPersistedPreparationSchedule,
            replacement.created_schedule_id,
        )
        if (
            replacement_schedule is None
            or replacement_schedule.household_id != household_id
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "accepted_replacement_schedule_missing",
                    "message": (
                        "Task execution eligibility cannot resolve the accepted "
                        "replacement schedule"
                    ),
                    "source_schedule_id": schedule.id,
                    "accepted_proposal_id": replacement.proposal_id,
                    "acceptance_id": replacement.id,
                    "replacement_schedule_id": replacement.created_schedule_id,
                },
            )
        return PreparationTaskExecutionEligibilityView(
            schedule_id=schedule.id,
            household_id=schedule.household_id,
            schedule_version=schedule.version,
            schedule_status=schedule.status,
            eligible=False,
            reason_code=(
                PreparationTaskExecutionEligibilityReason.
                SOURCE_HAS_ACCEPTED_REPLACEMENT
            ),
            task_event_count=task_event_count,
            accepted_proposal_id=replacement.proposal_id,
            acceptance_id=replacement.id,
            replacement_schedule_id=replacement_schedule.id,
            replacement_schedule_status=replacement_schedule.status,
            replacement_schedule_version=replacement_schedule.version,
        )

    if schedule.status != "approved":
        return PreparationTaskExecutionEligibilityView(
            schedule_id=schedule.id,
            household_id=schedule.household_id,
            schedule_version=schedule.version,
            schedule_status=schedule.status,
            eligible=False,
            reason_code=(
                PreparationTaskExecutionEligibilityReason.SCHEDULE_NOT_APPROVED
            ),
            task_event_count=task_event_count,
            accepted_proposal_id=None,
            acceptance_id=None,
            replacement_schedule_id=None,
            replacement_schedule_status=None,
            replacement_schedule_version=None,
        )

    return PreparationTaskExecutionEligibilityView(
        schedule_id=schedule.id,
        household_id=schedule.household_id,
        schedule_version=schedule.version,
        schedule_status=schedule.status,
        eligible=True,
        reason_code=PreparationTaskExecutionEligibilityReason.ELIGIBLE,
        task_event_count=task_event_count,
        accepted_proposal_id=None,
        acceptance_id=None,
        replacement_schedule_id=None,
        replacement_schedule_status=None,
        replacement_schedule_version=None,
    )


__all__ = ["get_task_execution_eligibility"]
