"""Authoritative creation for immutable preparation repair proposals.

Proposal creation is isolated here so exact request-key idempotency remains the
only uniqueness rule. Semantic hashes remain indexed evidence; distinct review
requests are not silently collapsed across different idempotency keys.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import utcnow
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.domain.preparation_repair import PreparationScheduleRepairRequest
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalCreateRequest,
    PreparationRepairProposalEventType,
    PreparationRepairProposalStatus,
    PreparationRepairProposalView,
)
from backend.engines.prep_schedule_repair import (
    PreparationRepairError,
    repair_preparation_schedule,
)
from backend.preparation_repair_proposal_models import DBPreparationRepairProposal
from backend.services.household_plan_lifecycle_service import assert_approved_source_plan
from backend.services.preparation_operations_service import (
    _assert_schedule_matches_calendar,
    _lock_household,
)
from backend.services.preparation_repair_proposal_read_service import _proposal_view
from backend.services.preparation_repair_proposal_service import (
    ACTIVE_SOURCE_STATUSES,
    _canonical_hash,
    _creation_fingerprint,
    _event,
    _load_source_payloads,
    _required_acknowledgements,
    _source_schedule,
    _target_calendar,
)


def create_repair_proposal(
    db: Session,
    *,
    household_id: str,
    actor_user_id: str,
    payload: PreparationRepairProposalCreateRequest,
) -> PreparationRepairProposalView:
    """Persist one complete, server-recomputed, non-accepted repair proposal."""

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
                    "Revised tasks no longer match retained occurrence/profile provenance"
                ),
                "errors": exc.errors(),
            },
        ) from exc

    repair_request_payload = repair_request.model_dump(mode="json")
    repair_result_payload = result.model_dump(mode="json")
    repair_request_hash = _canonical_hash(repair_request_payload)
    repair_result_hash = _canonical_hash(repair_result_payload)
    acknowledgements = _required_acknowledgements(result)
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
        required_acknowledgement_task_ids=acknowledgements,
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
            "required_acknowledgement_task_ids": acknowledgements,
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
                DBPreparationRepairProposal.household_id == household_id,
                DBPreparationRepairProposal.creation_idempotency_key
                == payload.idempotency_key,
            )
            .first()
        )
        if concurrent is not None:
            if concurrent.creation_request_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "repair_proposal_idempotency_conflict",
                        "message": (
                            "Repair proposal idempotency key was reused with different content"
                        ),
                    },
                ) from exc
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


__all__ = ["create_repair_proposal"]
