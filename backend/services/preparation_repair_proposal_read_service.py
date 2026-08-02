"""Execution-aware authoritative reads and rejection for repair proposals."""

from __future__ import annotations

from typing import Iterable, List

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import DBMealPlan, utcnow
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    PreparationScheduleStatus,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptanceView,
    PreparationRepairProposalEventType,
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
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)
from backend.services.preparation_operations_service import _lock_household
from backend.services.preparation_repair_proposal_service import (
    _event,
    _event_view,
    _proposal_result,
    _reject_fingerprint,
)


ACTIVE_SOURCE_STATUSES = {
    PreparationScheduleStatus.DRAFT.value,
    PreparationScheduleStatus.APPROVED.value,
}


def _acceptance_record(
    db: Session,
    proposal_id: int,
) -> DBPreparationRepairProposalAcceptance | None:
    return (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
        .first()
    )


def _acceptance_view(
    value: DBPreparationRepairProposalAcceptance,
) -> PreparationRepairProposalAcceptanceView:
    return PreparationRepairProposalAcceptanceView(
        id=value.id,
        household_id=value.household_id,
        proposal_id=value.proposal_id,
        proposal_version_before=value.proposal_version_before,
        proposal_version_after=value.proposal_version_after,
        source_schedule_id=value.source_schedule_id,
        source_schedule_version=value.source_schedule_version,
        created_schedule_id=value.created_schedule_id,
        created_schedule_version=value.created_schedule_version,
        created_schedule_status="draft",
        derivation_method=value.derivation_method,
        source_schedule_hash=value.source_schedule_hash,
        source_schedule_request_hash=value.source_schedule_request_hash,
        target_calendar_content_hash=value.target_calendar_content_hash,
        repair_request_hash=value.repair_request_hash,
        repair_result_hash=value.repair_result_hash,
        revised_request_hash=value.revised_request_hash,
        repaired_response_hash=value.repaired_response_hash,
        acknowledged_task_ids=sorted(value.acknowledged_task_ids or []),
        reason=value.reason,
        actor_user_id=value.actor_user_id,
        metadata=dict(value.acceptance_metadata or {}),
        idempotency_key=value.idempotency_key,
        request_fingerprint=value.request_fingerprint,
        created_at=value.created_at.isoformat(),
    )


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
    acceptance = _acceptance_record(db, proposal.id)
    is_accepted = proposal.status == PreparationRepairProposalStatus.ACCEPTED.value
    if is_accepted and acceptance is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_acceptance_evidence_missing",
                "message": "Accepted proposal lacks immutable acceptance evidence",
            },
        )
    if not is_accepted and acceptance is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_acceptance_state_mismatch",
                "message": "Non-accepted proposal has contradictory acceptance evidence",
            },
        )
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
        accepted=is_accepted,
        schedule_persistence_performed=is_accepted,
        accepted_schedule_id=(acceptance.created_schedule_id if acceptance else None),
        accepted_by_user_id=(acceptance.actor_user_id if acceptance else None),
        accepted_at=(acceptance.created_at.isoformat() if acceptance else None),
        acceptance_reason=(acceptance.reason if acceptance else None),
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


def get_repair_proposal_acceptance(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
) -> PreparationRepairProposalAcceptanceView:
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
    acceptance = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.proposal_id == proposal_id,
            DBPreparationRepairProposalAcceptance.household_id == household_id,
        )
        .first()
    )
    if acceptance is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return _acceptance_view(acceptance)


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
    _lock_household(db, household_id)
    proposal = (
        db.query(DBPreparationRepairProposal)
        .filter(
            DBPreparationRepairProposal.id == proposal_id,
            DBPreparationRepairProposal.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    fingerprint = _reject_fingerprint(
        payload,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=actor_user_id,
    )
    existing_event = (
        db.query(DBPreparationRepairProposalEvent)
        .filter(
            DBPreparationRepairProposalEvent.proposal_id == proposal_id,
            DBPreparationRepairProposalEvent.idempotency_key
            == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing_event is not None:
        if existing_event.request_fingerprint != fingerprint:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "repair_proposal_event_idempotency_conflict",
                    "message": (
                        "Repair proposal event key was reused with different content"
                    ),
                },
            )
        return _proposal_view(db, proposal)
    if proposal.version != payload.expected_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_version_mismatch",
                "message": "Repair proposal version changed",
                "expected_version": payload.expected_version,
                "actual_version": proposal.version,
            },
        )
    if proposal.status != PreparationRepairProposalStatus.PROPOSED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_not_rejectable",
                "message": "Only proposed repair records can be rejected",
                "status": proposal.status,
            },
        )

    before = proposal.version
    now = utcnow()
    proposal.status = PreparationRepairProposalStatus.REJECTED.value
    proposal.version += 1
    proposal.rejected_by_user_id = actor_user_id
    proposal.rejected_at = now
    proposal.rejection_reason = payload.reason
    proposal.updated_at = now
    db.add(proposal)
    _event(
        db,
        proposal=proposal,
        event_type=PreparationRepairProposalEventType.REJECTED,
        actor_user_id=actor_user_id,
        from_status=PreparationRepairProposalStatus.PROPOSED.value,
        to_status=PreparationRepairProposalStatus.REJECTED.value,
        reason=payload.reason,
        metadata=payload.metadata,
        proposal_version_before=before,
        proposal_version_after=proposal.version,
        idempotency_key=payload.idempotency_key,
        request_fingerprint=fingerprint,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_rejection_conflict",
                "message": "Repair proposal rejection conflicted with concurrent state",
            },
        ) from exc
    db.refresh(proposal)
    return _proposal_view(db, proposal)


__all__ = [
    "_acceptance_view",
    "_proposal_view",
    "_stale_reasons",
    "get_repair_proposal",
    "get_repair_proposal_acceptance",
    "list_repair_proposal_events",
    "list_repair_proposals",
    "reject_repair_proposal",
]
