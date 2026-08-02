"""Authoritative persistence for immutable preparation repair proposals.

Proposal creation recomputes repair on the server, validates the target calendar
and retained occurrence/profile provenance, and stores a hash-addressed review
record. It never creates, replaces, approves, completes, or executes a schedule.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, List

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import DBMealPlan, utcnow
from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    PreparationOccurrenceSetDocument,
    PreparationScheduleStatus,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.domain.preparation_repair import (
    PreparationScheduleRepairRequest,
    PreparationScheduleRepairResult,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalCreateRequest,
    PreparationRepairProposalEventType,
    PreparationRepairProposalEventView,
    PreparationRepairProposalRejectRequest,
    PreparationRepairProposalStatus,
    PreparationRepairProposalView,
)
from backend.engines.prep_schedule_repair import (
    PreparationRepairError,
    repair_preparation_schedule,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBResourceCalendarVersion,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalEvent,
)
from backend.services.household_plan_lifecycle_service import (
    assert_approved_source_plan,
)
from backend.services.preparation_operations_service import (
    _assert_schedule_matches_calendar,
    _lock_household,
)


ACTIVE_SOURCE_STATUSES = {
    PreparationScheduleStatus.DRAFT.value,
    PreparationScheduleStatus.APPROVED.value,
}


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _creation_fingerprint(
    payload: PreparationRepairProposalCreateRequest,
    *,
    household_id: str,
    actor_user_id: str,
) -> str:
    return _canonical_hash(
        {
            "household_id": household_id,
            "actor_user_id": actor_user_id,
            "payload": payload.model_dump(mode="json"),
        }
    )


def _reject_fingerprint(
    payload: PreparationRepairProposalRejectRequest,
    *,
    household_id: str,
    proposal_id: int,
    actor_user_id: str,
) -> str:
    return _canonical_hash(
        {
            "household_id": household_id,
            "proposal_id": proposal_id,
            "actor_user_id": actor_user_id,
            "payload": payload.model_dump(mode="json"),
        }
    )


def _load_source_payloads(
    source: DBPersistedPreparationSchedule,
) -> tuple[
    PreparationOccurrenceSetDocument,
    PreparationScheduleRequest,
    PreparationScheduleResponse,
]:
    if source.occurrence_set_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_source_occurrence_set_missing",
                "message": "Repair proposals require a complete occurrence document",
            },
        )
    if source.schedule_request_payload is None or source.schedule_request_hash is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_source_request_missing",
                "message": "Repair proposals require a replayable source request",
            },
        )
    try:
        occurrence_set = PreparationOccurrenceSetDocument.model_validate(
            source.occurrence_set_payload
        )
        previous_request = PreparationScheduleRequest.model_validate(
            source.schedule_request_payload
        )
        previous_response = PreparationScheduleResponse.model_validate(
            source.schedule_payload
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_source_provenance_invalid",
                "message": "Source schedule provenance no longer validates",
            },
        ) from exc
    if _canonical_hash(previous_request.model_dump(mode="json")) != source.schedule_request_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_source_request_hash_mismatch",
                "message": "Source request does not match its persisted hash",
            },
        )
    if previous_response.unscheduled:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_source_incomplete",
                "message": "Repair proposals require a complete source schedule",
            },
        )
    return occurrence_set, previous_request, previous_response


def _source_schedule(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    for_update: bool,
) -> DBPersistedPreparationSchedule:
    query = db.query(DBPersistedPreparationSchedule).filter(
        DBPersistedPreparationSchedule.id == schedule_id,
        DBPersistedPreparationSchedule.household_id == household_id,
    )
    if for_update:
        query = query.with_for_update()
    value = query.first()
    if value is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return value


def _target_calendar(
    db: Session,
    *,
    household_id: str,
    calendar_id: int,
    for_update: bool,
) -> DBResourceCalendarVersion:
    query = db.query(DBResourceCalendarVersion).filter(
        DBResourceCalendarVersion.id == calendar_id,
        DBResourceCalendarVersion.household_id == household_id,
    )
    if for_update:
        query = query.with_for_update()
    value = query.first()
    if value is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if (
        not value.active
        or value.evidence_status != CalendarEvidenceStatus.REVIEWED.value
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "active_reviewed_calendar_required",
                "message": (
                    "Repair proposals require the active reviewed target calendar"
                ),
            },
        )
    return value


def _required_acknowledgements(result: PreparationScheduleRepairResult) -> List[str]:
    identifiers = {
        *(value.task_id for value in result.moved_tasks),
        *result.added_task_ids,
        *result.removed_task_ids,
        *result.unscheduled_task_ids,
    }
    return sorted(identifiers)


def _event(
    db: Session,
    *,
    proposal: DBPreparationRepairProposal,
    event_type: PreparationRepairProposalEventType,
    actor_user_id: str,
    from_status: str | None,
    to_status: str,
    reason: str,
    metadata: dict,
    proposal_version_before: int,
    proposal_version_after: int,
    idempotency_key: str,
    request_fingerprint: str,
) -> DBPreparationRepairProposalEvent:
    value = DBPreparationRepairProposalEvent(
        proposal_id=proposal.id,
        household_id=proposal.household_id,
        event_type=event_type.value,
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        event_metadata=metadata,
        proposal_version_before=proposal_version_before,
        proposal_version_after=proposal_version_after,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        created_at=utcnow(),
    )
    db.add(value)
    db.flush()
    return value


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


def _proposal_result(
    proposal: DBPreparationRepairProposal,
) -> PreparationScheduleRepairResult:
    try:
        result = PreparationScheduleRepairResult.model_validate(
            proposal.repair_result_payload
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_payload_invalid",
                "message": "Persisted repair proposal result no longer validates",
            },
        ) from exc
    payload = result.model_dump(mode="json")
    if _canonical_hash(payload) != proposal.repair_result_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_result_hash_mismatch",
                "message": "Persisted repair proposal result does not match its hash",
            },
        )
    if result.revised_request_hash != proposal.revised_request_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_revised_hash_mismatch",
                "message": "Repair result revised-request hash differs from proposal",
            },
        )
    if result.repaired_response_hash != proposal.repaired_response_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_response_hash_mismatch",
                "message": "Repair result response hash differs from proposal",
            },
        )
    return result


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


def _event_view(
    value: DBPreparationRepairProposalEvent,
) -> PreparationRepairProposalEventView:
    return PreparationRepairProposalEventView(
        id=value.id,
        proposal_id=value.proposal_id,
        household_id=value.household_id,
        event_type=PreparationRepairProposalEventType(value.event_type),
        actor_user_id=value.actor_user_id,
        from_status=(
            PreparationRepairProposalStatus(value.from_status)
            if value.from_status
            else None
        ),
        to_status=PreparationRepairProposalStatus(value.to_status),
        reason=value.reason,
        metadata=dict(value.event_metadata or {}),
        proposal_version_before=value.proposal_version_before,
        proposal_version_after=value.proposal_version_after,
        idempotency_key=value.idempotency_key,
        request_fingerprint=value.request_fingerprint,
        created_at=value.created_at.isoformat(),
    )


def create_repair_proposal(
    db: Session,
    *,
    household_id: str,
    actor_user_id: str,
    payload: PreparationRepairProposalCreateRequest,
) -> PreparationRepairProposalView:
    _lock_household(db, household_id)
    fingerprint = _creation_fingerprint(
        payload,
        household_id=household_id,
        actor_user_id=actor_user_id,
    )
    existing = (
        db.query(DBPreparationRepairProposal)
        .filter(
            DBPreparationRepairProposal.household_id == household_id,
            DBPreparationRepairProposal.creation_idempotency_key
            == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing is not None:
        if existing.creation_request_fingerprint != fingerprint:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "repair_proposal_idempotency_conflict",
                    "message": (
                        "Repair proposal idempotency key was reused with different content"
                    ),
                },
            )
        return _proposal_view(db, existing)

    source = _source_schedule(
        db,
        household_id=household_id,
        schedule_id=payload.source_schedule_id,
        for_update=True,
    )
    if source.version != payload.expected_source_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_source_version_mismatch",
                "message": "Source schedule version changed before proposal creation",
                "expected_version": payload.expected_source_version,
                "actual_version": source.version,
            },
        )
    if source.status not in ACTIVE_SOURCE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_source_status_not_supported",
                "message": "Only replayable draft or approved schedules can be repaired",
                "status": source.status,
            },
        )

    occurrence_set, previous_request, previous_response = _load_source_payloads(
        source
    )
    assert_approved_source_plan(
        db,
        household_id=household_id,
        source_plan_id=source.source_plan_id,
        source_plan_version=source.source_plan_version,
    )
    calendar = _target_calendar(
        db,
        household_id=household_id,
        calendar_id=payload.target_calendar_version_id,
        for_update=True,
    )
    _assert_schedule_matches_calendar(db, calendar, payload.revised_request)

    repair_request = PreparationScheduleRepairRequest(
        previous_request=previous_request,
        previous_response=previous_response,
        revised_request=payload.revised_request,
        immutable_task_ids=payload.immutable_task_ids,
        strategy=payload.strategy,
        allow_partial=False,
        weights=payload.weights,
        exact_task_limit=payload.exact_task_limit,
        exact_candidate_limit_per_task=payload.exact_candidate_limit_per_task,
    )
    try:
        result = repair_preparation_schedule(repair_request)
    except PreparationRepairError as exc:
        raise HTTPException(status_code=409, detail=exc.as_dict()) from exc
    if not result.complete or result.unscheduled_task_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_requires_complete_result",
                "message": "Persisted repair proposals must be complete",
                "unscheduled_task_ids": result.unscheduled_task_ids,
            },
        )

    try:
        PersistedScheduleCreateRequest.model_validate(
            {
                "calendar_version_id": calendar.id,
                "source_plan_id": source.source_plan_id,
                "source_plan_version": source.source_plan_version,
                "occurrence_set": occurrence_set.model_dump(mode="json"),
                "profile_versions": dict(source.profile_versions or {}),
                "schedule_request": payload.revised_request.model_dump(mode="json"),
                "schedule_response": result.response.model_dump(mode="json"),
                "notes": payload.notes,
                "idempotency_key": payload.idempotency_key,
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "repair_proposal_provenance_mismatch",
                "message": (
                    "Revised tasks no longer match the retained occurrence and profile provenance"
                ),
                "errors": exc.errors(),
            },
        ) from exc

    repair_request_payload = repair_request.model_dump(mode="json")
    repair_result_payload = result.model_dump(mode="json")
    repair_request_hash = _canonical_hash(repair_request_payload)
    repair_result_hash = _canonical_hash(repair_result_payload)
    semantic = (
        db.query(DBPreparationRepairProposal)
        .filter(
            DBPreparationRepairProposal.source_schedule_id == source.id,
            DBPreparationRepairProposal.source_schedule_version == source.version,
            DBPreparationRepairProposal.revised_request_hash
            == result.revised_request_hash,
            DBPreparationRepairProposal.repaired_response_hash
            == result.repaired_response_hash,
        )
        .with_for_update()
        .first()
    )
    if semantic is not None:
        return _proposal_view(db, semantic)

    now = utcnow()
    proposal = DBPreparationRepairProposal(
        household_id=household_id,
        source_schedule_id=source.id,
        source_schedule_version=source.version,
        source_schedule_hash=source.schedule_hash,
        source_schedule_request_hash=source.schedule_request_hash,
        target_calendar_version_id=calendar.id,
        target_calendar_content_hash=calendar.content_hash,
        repair_request_payload=repair_request_payload,
        repair_request_hash=repair_request_hash,
        repair_result_payload=repair_result_payload,
        repair_result_hash=repair_result_hash,
        revised_request_hash=result.revised_request_hash,
        repaired_response_hash=result.repaired_response_hash,
        required_acknowledgement_task_ids=_required_acknowledgements(result),
        status=PreparationRepairProposalStatus.PROPOSED.value,
        version=1,
        notes=payload.notes,
        created_by_user_id=actor_user_id,
        rejected_by_user_id=None,
        rejected_at=None,
        rejection_reason=None,
        creation_idempotency_key=payload.idempotency_key,
        creation_request_fingerprint=fingerprint,
        created_at=now,
        updated_at=now,
    )
    db.add(proposal)
    db.flush()
    _event(
        db,
        proposal=proposal,
        event_type=PreparationRepairProposalEventType.CREATED,
        actor_user_id=actor_user_id,
        from_status=None,
        to_status=PreparationRepairProposalStatus.PROPOSED.value,
        reason="Server-recomputed preparation repair proposal created",
        metadata={
            "source_schedule_id": source.id,
            "source_schedule_version": source.version,
            "source_schedule_hash": source.schedule_hash,
            "target_calendar_version_id": calendar.id,
            "target_calendar_content_hash": calendar.content_hash,
            "repair_request_hash": repair_request_hash,
            "repair_result_hash": repair_result_hash,
            "revised_request_hash": result.revised_request_hash,
            "repaired_response_hash": result.repaired_response_hash,
            "required_acknowledgement_task_ids": _required_acknowledgements(
                result
            ),
            "accepted": False,
            "schedule_persistence_performed": False,
        },
        proposal_version_before=0,
        proposal_version_after=1,
        idempotency_key=f"repair-proposal-created:{proposal.id}",
        request_fingerprint=fingerprint,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        concurrent = (
            db.query(DBPreparationRepairProposal)
            .filter(
                DBPreparationRepairProposal.source_schedule_id == source.id,
                DBPreparationRepairProposal.source_schedule_version
                == source.version,
                DBPreparationRepairProposal.revised_request_hash
                == result.revised_request_hash,
                DBPreparationRepairProposal.repaired_response_hash
                == result.repaired_response_hash,
            )
            .first()
        )
        if concurrent is not None:
            return _proposal_view(db, concurrent)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_creation_conflict",
                "message": "Repair proposal creation conflicted with concurrent state",
            },
        ) from exc
    db.refresh(proposal)
    return _proposal_view(db, proposal)


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
