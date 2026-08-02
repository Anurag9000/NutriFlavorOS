"""Authoritative approval dispatcher for original and repaired schedule drafts.

Original deterministic drafts retain the established transition service.
Repair-derived drafts use their immutable proposal/acceptance evidence and the
method-aware repair replay before the ordinary draft-to-approved mutation.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import utcnow
from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    PersistedPreparationScheduleView,
    PreparationOccurrenceSetDocument,
    PreparationScheduleEventType,
    PreparationScheduleStatus,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.domain.preparation_repair import (
    PreparationScheduleRepairRequest,
    PreparationScheduleRepairResult,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalStatus,
)
from backend.domain.preparation_schedule_replay import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
    PreparationScheduleDerivationMethod,
    RepairedPreparationScheduleReplay,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)
from backend.services.household_plan_lifecycle_service import (
    assert_approved_source_plan,
)
from backend.services.preparation_operations_service import (
    _append_event,
    _assert_occurrence_household,
    _assert_schedule_matches_calendar,
    _lock_household,
    _schedule_hash,
    _schedule_view,
    _transition_fingerprint,
    transition_schedule,
)
from backend.services.preparation_repair_proposal_acceptance_service import (
    _repaired_combined_schedule_hash,
)
from backend.services.preparation_repair_proposal_service import _canonical_hash
from backend.services.preparation_schedule_replay_service import (
    PreparationScheduleReplayError,
    replay_preparation_schedule,
)


def _parse_schedule_provenance(
    schedule: DBPersistedPreparationSchedule,
) -> tuple[
    PreparationOccurrenceSetDocument,
    PreparationScheduleRequest,
    PreparationScheduleResponse,
]:
    if schedule.occurrence_set_payload is None or schedule.schedule_request_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_replay_input_missing",
                "message": "Schedule lacks complete occurrence and request provenance",
            },
        )
    try:
        occurrence_set = PreparationOccurrenceSetDocument.model_validate(
            schedule.occurrence_set_payload
        )
        request = PreparationScheduleRequest.model_validate(
            schedule.schedule_request_payload
        )
        response = PreparationScheduleResponse.model_validate(
            schedule.schedule_payload
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_provenance_validation_failed",
                "message": "Persisted schedule provenance no longer validates",
            },
        ) from exc
    return occurrence_set, request, response


def _validate_repaired_approval_replay(
    db: Session,
    *,
    household_id: str,
    schedule: DBPersistedPreparationSchedule,
    calendar: DBResourceCalendarVersion,
) -> None:
    if schedule.source_repair_proposal_id is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_proposal_link_missing",
                "message": "Repair-derived schedule lacks its source proposal",
            },
        )
    proposal = (
        db.query(DBPreparationRepairProposal)
        .filter(
            DBPreparationRepairProposal.id == schedule.source_repair_proposal_id,
            DBPreparationRepairProposal.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    acceptance = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.proposal_id == proposal.id,
            DBPreparationRepairProposalAcceptance.household_id == household_id,
            DBPreparationRepairProposalAcceptance.created_schedule_id == schedule.id,
        )
        .with_for_update()
        .first()
    )
    if acceptance is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_acceptance_missing",
                "message": "Repair-derived draft lacks immutable acceptance evidence",
            },
        )
    if proposal.status != PreparationRepairProposalStatus.ACCEPTED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_proposal_not_accepted",
                "message": "Repair-derived draft source proposal is not accepted",
                "status": proposal.status,
            },
        )

    exact_pairs = [
        (
            "proposal_version",
            schedule.source_repair_proposal_version,
            proposal.version,
        ),
        (
            "acceptance_proposal_version",
            acceptance.proposal_version_after,
            proposal.version,
        ),
        (
            "repair_request_hash",
            schedule.source_repair_request_hash,
            proposal.repair_request_hash,
        ),
        (
            "repair_result_hash",
            schedule.source_repair_result_hash,
            proposal.repair_result_hash,
        ),
        (
            "revised_request_hash",
            schedule.source_revised_request_hash,
            proposal.revised_request_hash,
        ),
        (
            "repaired_response_hash",
            schedule.source_repaired_response_hash,
            proposal.repaired_response_hash,
        ),
        (
            "acceptance_source_schedule_hash",
            acceptance.source_schedule_hash,
            proposal.source_schedule_hash,
        ),
        (
            "acceptance_calendar_hash",
            acceptance.target_calendar_content_hash,
            proposal.target_calendar_content_hash,
        ),
    ]
    for field, expected, observed in exact_pairs:
        if expected != observed:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "repair_schedule_derivation_mismatch",
                    "message": f"Repair-derived schedule {field} no longer agrees",
                    "field": field,
                    "expected": expected,
                    "observed": observed,
                },
            )

    source = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == proposal.source_schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if (
        source.version != proposal.source_schedule_version
        or source.schedule_hash != proposal.source_schedule_hash
        or source.schedule_request_hash != proposal.source_schedule_request_hash
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_source_stale",
                "message": "Source schedule changed after repair acceptance",
            },
        )
    execution_exists = (
        db.query(DBPreparationTaskExecutionEvent.id)
        .filter(DBPreparationTaskExecutionEvent.schedule_id == source.id)
        .with_for_update()
        .first()
        is not None
    )
    if execution_exists:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_source_has_execution_history",
                "message": "Source execution began after repair acceptance",
            },
        )

    occurrence_set, request, response = _parse_schedule_provenance(schedule)
    _assert_occurrence_household(occurrence_set, household_id)
    _assert_schedule_matches_calendar(db, calendar, request)
    assert_approved_source_plan(
        db,
        household_id=household_id,
        source_plan_id=schedule.source_plan_id,
        source_plan_version=schedule.source_plan_version,
    )
    try:
        verified = PersistedScheduleCreateRequest.model_validate(
            {
                "calendar_version_id": schedule.calendar_version_id,
                "source_plan_id": schedule.source_plan_id,
                "source_plan_version": schedule.source_plan_version,
                "occurrence_set": occurrence_set.model_dump(mode="json"),
                "profile_versions": dict(schedule.profile_versions or {}),
                "schedule_request": request.model_dump(mode="json"),
                "schedule_response": response.model_dump(mode="json"),
                "notes": schedule.notes,
                "idempotency_key": schedule.creation_idempotency_key,
            }
        )
        repair_request = PreparationScheduleRepairRequest.model_validate(
            proposal.repair_request_payload
        )
        repair_result = PreparationScheduleRepairResult.model_validate(
            proposal.repair_result_payload
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_provenance_invalid",
                "message": "Repair-derived schedule or proposal provenance is invalid",
            },
        ) from exc

    request_hash = _canonical_hash(request.model_dump(mode="json"))
    if request_hash != schedule.schedule_request_hash or request_hash != proposal.revised_request_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_request_hash_mismatch",
                "message": "Repair-derived schedule request hash no longer agrees",
            },
        )
    if verified.occurrence_set_hash != schedule.occurrence_set_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_occurrence_hash_mismatch",
                "message": "Repair-derived occurrence document hash no longer agrees",
            },
        )
    if _canonical_hash(repair_request.model_dump(mode="json")) != proposal.repair_request_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_repair_request_hash_mismatch",
                "message": "Repair request differs from proposal evidence",
            },
        )
    if _canonical_hash(repair_result.model_dump(mode="json")) != proposal.repair_result_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_repair_result_hash_mismatch",
                "message": "Repair result differs from proposal evidence",
            },
        )
    if response.model_dump(mode="json") != repair_result.response.model_dump(mode="json"):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_response_mismatch",
                "message": "Persisted repaired response differs from proposal result",
            },
        )

    try:
        replay = replay_preparation_schedule(
            method=PreparationScheduleDerivationMethod.REPAIR,
            repair=RepairedPreparationScheduleReplay(
                repair_request=repair_request,
                expected_result=repair_result,
                expected_repair_request_hash=proposal.repair_request_hash,
                expected_repair_result_hash=proposal.repair_result_hash,
                expected_revised_request_hash=proposal.revised_request_hash,
                expected_response_hash=proposal.repaired_response_hash,
            ),
        )
    except PreparationScheduleReplayError as exc:
        raise HTTPException(status_code=409, detail=exc.as_dict()) from exc
    if replay.replayed_response.model_dump(mode="json") != response.model_dump(mode="json"):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_approval_replay_mismatch",
                "message": "Repair approval replay differs from persisted response",
            },
        )

    base_hash = _schedule_hash(
        calendar_content_hash=calendar.content_hash,
        source_plan_id=schedule.source_plan_id,
        source_plan_version=schedule.source_plan_version,
        occurrence_set_version=verified.occurrence_set_version,
        occurrence_set_hash=verified.occurrence_set_hash,
        profile_versions=verified.profile_versions,
        schedule_request=request,
        schedule_response=replay.replayed_response,
    )
    expected_schedule_hash = _repaired_combined_schedule_hash(
        base_schedule_hash=base_hash,
        proposal=proposal,
        accepted_proposal_version=proposal.version,
    )
    if expected_schedule_hash != schedule.schedule_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_schedule_hash_mismatch",
                "message": "Repair-derived combined schedule hash no longer agrees",
            },
        )


def approve_schedule_authoritative(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    payload: ScheduleStateTransitionRequest,
) -> PersistedPreparationScheduleView:
    preview = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if preview is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    method = preview.derivation_method or ORIGINAL_SCHEDULER_METHOD
    if method == ORIGINAL_SCHEDULER_METHOD:
        return transition_schedule(
            db,
            household_id=household_id,
            schedule_id=schedule_id,
            actor_user_id=actor_user_id,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=payload,
        )
    if method != REPAIR_SCHEDULER_METHOD:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "unknown_schedule_derivation_method",
                "message": "Schedule derivation method is not supported",
                "method": method,
            },
        )

    _lock_household(db, household_id)
    fingerprint = _transition_fingerprint(
        schedule_id,
        PreparationScheduleEventType.APPROVED,
        payload,
        actor_user_id,
    )
    existing_event = (
        db.query(DBPreparationScheduleEvent)
        .filter(
            DBPreparationScheduleEvent.household_id == household_id,
            DBPreparationScheduleEvent.idempotency_key == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing_event is not None:
        if (
            existing_event.schedule_id != schedule_id
            or existing_event.event_type != PreparationScheduleEventType.APPROVED.value
            or existing_event.request_fingerprint != fingerprint
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "schedule_event_idempotency_conflict",
                    "message": "Schedule approval key was reused with different content",
                },
            )
        schedule = db.get(DBPersistedPreparationSchedule, schedule_id)
        if schedule is None or schedule.household_id != household_id:
            raise HTTPException(status_code=404, detail="Resource not found")
        return _schedule_view(schedule)

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
    if schedule.version != payload.expected_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_version_conflict",
                "message": "Schedule version changed; reload before approval",
                "current_version": schedule.version,
            },
        )
    if schedule.status != PreparationScheduleStatus.DRAFT.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_schedule_transition",
                "message": "Only draft schedules can be approved",
            },
        )
    calendar = (
        db.query(DBResourceCalendarVersion)
        .filter(DBResourceCalendarVersion.id == schedule.calendar_version_id)
        .with_for_update()
        .first()
    )
    if (
        calendar is None
        or not calendar.active
        or calendar.household_id != household_id
        or calendar.content_hash != schedule.calendar_content_hash
        or calendar.evidence_status != CalendarEvidenceStatus.REVIEWED.value
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_calendar_stale",
                "message": "Schedule calendar is no longer the active reviewed version",
            },
        )
    _validate_repaired_approval_replay(
        db,
        household_id=household_id,
        schedule=schedule,
        calendar=calendar,
    )

    now = utcnow()
    schedule.status = PreparationScheduleStatus.APPROVED.value
    schedule.version += 1
    schedule.approved_by_user_id = actor_user_id
    schedule.approved_at = now
    schedule.updated_at = now
    db.add(schedule)
    _append_event(
        db,
        schedule=schedule,
        event_type=PreparationScheduleEventType.APPROVED,
        actor_user_id=actor_user_id,
        from_status=PreparationScheduleStatus.DRAFT.value,
        to_status=PreparationScheduleStatus.APPROVED.value,
        reason=payload.reason,
        metadata={
            **payload.metadata,
            "derivation_method": REPAIR_SCHEDULER_METHOD,
            "source_repair_proposal_id": schedule.source_repair_proposal_id,
            "source_repair_proposal_version": schedule.source_repair_proposal_version,
            "repair_request_hash": schedule.source_repair_request_hash,
            "repair_result_hash": schedule.source_repair_result_hash,
            "revised_request_hash": schedule.source_revised_request_hash,
            "repaired_response_hash": schedule.source_repaired_response_hash,
            "method_aware_replay_verified": True,
        },
        idempotency_key=payload.idempotency_key,
        request_fingerprint=fingerprint,
        created_at=now,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_transition_conflict",
                "message": "Schedule approval conflicted with concurrent state",
            },
        ) from exc
    db.refresh(schedule)
    return _schedule_view(schedule)


__all__ = ["approve_schedule_authoritative"]
