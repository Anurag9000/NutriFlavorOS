"""Execution-aware authoritative reads for preparation repair proposals."""

from __future__ import annotations

from typing import Iterable, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database import DBMealPlan
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    PreparationScheduleStatus,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalEventView,
    PreparationRepairProposalRejectRequest,
    PreparationRepairProposalStatus,
    PreparationRepairProposalView,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBResourceCalendarVersion,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalEvent,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)
from backend.services.preparation_repair_proposal_service import (
    _event_view,
    _proposal_result,
    reject_repair_proposal as _reject_repair_proposal,
)


ACTIVE_SOURCE_STATUSES = {
    PreparationScheduleStatus.DRAFT.value,
    PreparationScheduleStatus.APPROVED.value,
}


def _stale_reasons(
    db: Session,
    proposal: DBPreparationRepairProposal,
) -> List[str]:
    reasons: List[str] = []
    if proposal.status != PreparationRepairProposalStatus.PROPOSED.value:
        reasons.append(f"proposal_status_{proposal.status}")

    source = db.get(DBPersistedPreparationSchedule, proposal.source_schedule_id)
    if source is None or source.household_id != proposal.household_id:
        reasons.append("source_schedule_missing")
    else:
        if source.version != proposal.source_schedule_version:
            reasons.append("source_schedule_version_changed")
        if source.schedule_hash != proposal.source_schedule_hash:
            reasons.append("source_schedule_hash_changed")
        if source.schedule_request_hash != proposal.source_schedule_request_hash:
            reasons.append("source_schedule_request_hash_changed")
        if source.status not in ACTIVE_SOURCE_STATUSES:
            reasons.append(f"source_schedule_status_{source.status}")
        execution_exists = (
            db.query(DBPreparationTaskExecutionEvent.id)
            .filter(DBPreparationTaskExecutionEvent.schedule_id == source.id)
            .first()
            is not None
        )
        if execution_exists:
            reasons.append("source_schedule_has_execution_history")
        if source.source_plan_id is not None:
            plan = db.get(DBMealPlan, source.source_plan_id)
            if (
                plan is None
                or plan.household_id != proposal.household_id
                or plan.version != source.source_plan_version
                or getattr(plan, "status", None) != "approved"
            ):
                reasons.append("source_plan_not_currently_approved")

    calendar = db.get(
        DBResourceCalendarVersion,
        proposal.target_calendar_version_id,
    )
    if calendar is None or calendar.household_id != proposal.household_id:
        reasons.append("target_calendar_missing")
    else:
        if calendar.content_hash != proposal.target_calendar_content_hash:
            reasons.append("target_calendar_hash_changed")
        if not calendar.active:
            reasons.append("target_calendar_not_active")
        if calendar.evidence_status != CalendarEvidenceStatus.REVIEWED.value:
            reasons.append("target_calendar_not_reviewed")
    return sorted(set(reasons))


def _proposal_view(
    db: Session,
    proposal: DBPreparationRepairProposal,
) -> PreparationRepairProposalView:
    stale = _stale_reasons(db, proposal)
    return PreparationRepairProposalView(
        id=proposal.id,
        household_id=proposal.household_id,
        source_schedule_id=proposal.source_schedule_id,
        source_schedule_version=proposal.source_schedule_version,
        source_schedule_hash=proposal.source_schedule_hash,
        source_schedule_request_hash=proposal.source_schedule_request_hash,
        target_calendar_version_id=proposal.target_calendar_version_id,
        target_calendar_content_hash=proposal.target_calendar_content_hash,
        repair_request_hash=proposal.repair_request_hash,
        repair_result_hash=proposal.repair_result_hash,
        revised_request_hash=proposal.revised_request_hash,
        repaired_response_hash=proposal.repaired_response_hash,
        required_acknowledgement_task_ids=sorted(
            proposal.required_acknowledgement_task_ids or []
        ),
        repair_result=_proposal_result(proposal),
        status=PreparationRepairProposalStatus(proposal.status),
        version=proposal.version,
        notes=proposal.notes,
        created_by_user_id=proposal.created_by_user_id,
        rejected_by_user_id=proposal.rejected_by_user_id,
        rejected_at=(
            proposal.rejected_at.isoformat() if proposal.rejected_at else None
        ),
        rejection_reason=proposal.rejection_reason,
        current=not stale,
        stale_reasons=stale,
        accepted=False,
        schedule_persistence_performed=False,
        created_at=proposal.created_at.isoformat(),
        updated_at=proposal.updated_at.isoformat(),
    )


def list_repair_proposals(
    db: Session,
    *,
    household_id: str,
    statuses: Iterable[PreparationRepairProposalStatus] | None = None,
) -> List[PreparationRepairProposalView]:
    query = db.query(DBPreparationRepairProposal).filter(
        DBPreparationRepairProposal.household_id == household_id
    )
    if statuses:
        query = query.filter(
            DBPreparationRepairProposal.status.in_(
                [value.value for value in statuses]
            )
        )
    rows = query.order_by(
        DBPreparationRepairProposal.updated_at.desc(),
        DBPreparationRepairProposal.id.desc(),
    ).all()
    return [_proposal_view(db, value) for value in rows]


def get_repair_proposal(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
) -> PreparationRepairProposalView:
    value = (
        db.query(DBPreparationRepairProposal)
        .filter(
            DBPreparationRepairProposal.id == proposal_id,
            DBPreparationRepairProposal.household_id == household_id,
        )
        .first()
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return _proposal_view(db, value)


def list_repair_proposal_events(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
) -> List[PreparationRepairProposalEventView]:
    proposal = (
        db.query(DBPreparationRepairProposal.id)
        .filter(
            DBPreparationRepairProposal.id == proposal_id,
            DBPreparationRepairProposal.household_id == household_id,
        )
        .first()
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    rows = (
        db.query(DBPreparationRepairProposalEvent)
        .filter(
            DBPreparationRepairProposalEvent.proposal_id == proposal_id,
            DBPreparationRepairProposalEvent.household_id == household_id,
        )
        .order_by(
            DBPreparationRepairProposalEvent.created_at.asc(),
            DBPreparationRepairProposalEvent.id.asc(),
        )
        .all()
    )
    return [_event_view(value) for value in rows]


def reject_repair_proposal(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
    actor_user_id: str,
    payload: PreparationRepairProposalRejectRequest,
) -> PreparationRepairProposalView:
    _reject_repair_proposal(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )
    return get_repair_proposal(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
    )


__all__ = [
    "_proposal_view",
    "get_repair_proposal",
    "list_repair_proposal_events",
    "list_repair_proposals",
    "reject_repair_proposal",
]
