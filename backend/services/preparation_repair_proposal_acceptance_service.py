"""Atomic acceptance of one repair proposal into one new preparation draft.

Acceptance is separate from advisory computation and separate from schedule
approval. The transaction revalidates every source identity, requires exact
changed-task acknowledgements, reruns method-aware repair replay, creates one
new draft, and appends immutable proposal and schedule events. It never mutates
the source schedule and never records task execution or completion.
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
    PreparationOccurrenceSetDocument,
    PreparationScheduleEventType,
    PreparationScheduleStatus,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.domain.preparation_repair import (
    PreparationScheduleRepairRequest,
    PreparationScheduleRepairResult,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
    PreparationRepairProposalAcceptedDraftView,
    PreparationRepairProposalEventType,
    PreparationRepairProposalStatus,
)
from backend.domain.preparation_schedule_replay import (
    REPAIR_SCHEDULER_METHOD,
    PreparationScheduleDerivationMethod,
    RepairedPreparationScheduleReplay,
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
from backend.services.household_plan_lifecycle_service import (
    assert_approved_source_plan,
)
from backend.services.preparation_operations_service import (
    _append_event,
    _assert_occurrence_household,
    _assert_schedule_matches_calendar,
    _lock_household,
    _schedule_hash,
)
from backend.services.preparation_repair_proposal_read_service import (
    _acceptance_view,
    _proposal_view,
)
from backend.services.preparation_repair_proposal_service import (
    _canonical_hash,
    _event,
)
from backend.services.preparation_schedule_replay_service import (
    PreparationScheduleReplayError,
    replay_preparation_schedule,
)


ACTIVE_SOURCE_STATUSES = {
    PreparationScheduleStatus.DRAFT.value,
    PreparationScheduleStatus.APPROVED.value,
}


def _acceptance_fingerprint(
    payload: PreparationRepairProposalAcceptRequest,
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


def _accepted_draft_view(
    db: Session,
    *,
    proposal: DBPreparationRepairProposal,
    acceptance: DBPreparationRepairProposalAcceptance,
) -> PreparationRepairProposalAcceptedDraftView:
    return PreparationRepairProposalAcceptedDraftView(
        proposal=_proposal_view(db, proposal),
        acceptance=_acceptance_view(db, acceptance),
        accepted=True,
        schedule_persistence_performed=True,
        approval_performed=False,
        execution_performed=False,
    )


def _identity_conflict(
    *,
    field: str,
    expected: object,
    observed: object,
) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "repair_acceptance_identity_mismatch",
            "message": f"Repair acceptance {field} changed",
            "field": field,
            "expected": expected,
            "observed": observed,
        },
    )


def _parse_proposal_payloads(
    proposal: DBPreparationRepairProposal,
) -> tuple[PreparationScheduleRepairRequest, PreparationScheduleRepairResult]:
    try:
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
                "code": "repair_acceptance_proposal_payload_invalid",
                "message": "Repair proposal request or result no longer validates",
            },
        ) from exc
    if _canonical_hash(repair_request.model_dump(mode="json")) != proposal.repair_request_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_request_hash_mismatch",
                "message": "Repair proposal request differs from its persisted hash",
            },
        )
    if _canonical_hash(repair_result.model_dump(mode="json")) != proposal.repair_result_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_result_hash_mismatch",
                "message": "Repair proposal result differs from its persisted hash",
            },
        )
    return repair_request, repair_result


def _parse_source_provenance(
    source: DBPersistedPreparationSchedule,
) -> tuple[
    PreparationOccurrenceSetDocument,
    PreparationScheduleRequest,
    PreparationScheduleResponse,
]:
    if source.occurrence_set_payload is None or source.schedule_request_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_source_provenance_missing",
                "message": "Source schedule lacks complete replay provenance",
            },
        )
    try:
        occurrence_set = PreparationOccurrenceSetDocument.model_validate(
            source.occurrence_set_payload
        )
        source_request = PreparationScheduleRequest.model_validate(
            source.schedule_request_payload
        )
        source_response = PreparationScheduleResponse.model_validate(
            source.schedule_payload
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_source_provenance_invalid",
                "message": "Source schedule provenance no longer validates",
            },
        ) from exc
    return occurrence_set, source_request, source_response


def _repaired_combined_schedule_hash(
    *,
    base_schedule_hash: str,
    proposal: DBPreparationRepairProposal,
    accepted_proposal_version: int,
) -> str:
    return _canonical_hash(
        {
            "base_schedule_hash": base_schedule_hash,
            "derivation_method": REPAIR_SCHEDULER_METHOD,
            "source_repair_proposal_id": proposal.id,
            "source_repair_proposal_version": accepted_proposal_version,
            "source_repair_request_hash": proposal.repair_request_hash,
            "source_repair_result_hash": proposal.repair_result_hash,
            "source_revised_request_hash": proposal.revised_request_hash,
            "source_repaired_response_hash": proposal.repaired_response_hash,
        }
    )


def accept_repair_proposal(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
    actor_user_id: str,
    payload: PreparationRepairProposalAcceptRequest,
) -> PreparationRepairProposalAcceptedDraftView:
    _lock_household(db, household_id)
    fingerprint = _acceptance_fingerprint(
        payload,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=actor_user_id,
    )

    existing_by_key = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.household_id == household_id,
            DBPreparationRepairProposalAcceptance.idempotency_key
            == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing_by_key is not None:
        if (
            existing_by_key.proposal_id != proposal_id
            or existing_by_key.request_fingerprint != fingerprint
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "repair_acceptance_idempotency_conflict",
                    "message": (
                        "Repair acceptance idempotency key was reused with different content"
                    ),
                },
            )
        proposal = db.get(DBPreparationRepairProposal, proposal_id)
        if proposal is None or proposal.household_id != household_id:
            raise HTTPException(status_code=404, detail="Resource not found")
        return _accepted_draft_view(
            db,
            proposal=proposal,
            acceptance=existing_by_key,
        )

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
    existing_for_proposal = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .with_for_update()
        .first()
    )
    if existing_for_proposal is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_already_accepted",
                "message": "Repair proposal already created a draft under another request key",
                "created_schedule_id": existing_for_proposal.created_schedule_id,
            },
        )
    conflicting_event = (
        db.query(DBPreparationRepairProposalEvent.id)
        .filter(
            DBPreparationRepairProposalEvent.proposal_id == proposal.id,
            DBPreparationRepairProposalEvent.idempotency_key
            == payload.idempotency_key,
        )
        .first()
    )
    if conflicting_event is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_event_key_conflict",
                "message": "Acceptance key is already used by another proposal event",
            },
        )
    if proposal.version != payload.expected_proposal_version:
        raise _identity_conflict(
            field="proposal_version",
            expected=payload.expected_proposal_version,
            observed=proposal.version,
        )
    if proposal.status != PreparationRepairProposalStatus.PROPOSED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_proposal_not_acceptable",
                "message": "Only current proposed repair records can be accepted",
                "status": proposal.status,
            },
        )

    identity_pairs = [
        (
            "source_schedule_version",
            payload.expected_source_schedule_version,
            proposal.source_schedule_version,
        ),
        (
            "source_schedule_hash",
            payload.expected_source_schedule_hash,
            proposal.source_schedule_hash,
        ),
        (
            "source_schedule_request_hash",
            payload.expected_source_schedule_request_hash,
            proposal.source_schedule_request_hash,
        ),
        (
            "target_calendar_content_hash",
            payload.expected_target_calendar_content_hash,
            proposal.target_calendar_content_hash,
        ),
        (
            "repair_request_hash",
            payload.expected_repair_request_hash,
            proposal.repair_request_hash,
        ),
        (
            "repair_result_hash",
            payload.expected_repair_result_hash,
            proposal.repair_result_hash,
        ),
        (
            "revised_request_hash",
            payload.expected_revised_request_hash,
            proposal.revised_request_hash,
        ),
        (
            "repaired_response_hash",
            payload.expected_repaired_response_hash,
            proposal.repaired_response_hash,
        ),
    ]
    for field, expected, observed in identity_pairs:
        if expected != observed:
            raise _identity_conflict(
                field=field,
                expected=expected,
                observed=observed,
            )

    required_acknowledgements = sorted(
        proposal.required_acknowledgement_task_ids or []
    )
    if payload.acknowledged_task_ids != required_acknowledgements:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_acknowledgement_mismatch",
                "message": "Acknowledged task IDs must exactly match all changed tasks",
                "required": required_acknowledgements,
                "observed": payload.acknowledged_task_ids,
                "missing": sorted(
                    set(required_acknowledgements)
                    - set(payload.acknowledged_task_ids)
                ),
                "unexpected": sorted(
                    set(payload.acknowledged_task_ids)
                    - set(required_acknowledgements)
                ),
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
    if source.version != proposal.source_schedule_version:
        raise _identity_conflict(
            field="live_source_schedule_version",
            expected=proposal.source_schedule_version,
            observed=source.version,
        )
    if source.schedule_hash != proposal.source_schedule_hash:
        raise _identity_conflict(
            field="live_source_schedule_hash",
            expected=proposal.source_schedule_hash,
            observed=source.schedule_hash,
        )
    if source.schedule_request_hash != proposal.source_schedule_request_hash:
        raise _identity_conflict(
            field="live_source_schedule_request_hash",
            expected=proposal.source_schedule_request_hash,
            observed=source.schedule_request_hash,
        )
    if source.status not in ACTIVE_SOURCE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_source_status_changed",
                "message": "Source schedule is no longer draft or approved",
                "status": source.status,
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
                "code": "repair_acceptance_source_has_execution_history",
                "message": (
                    "Execution-aware repair is not implemented; acceptance cannot "
                    "proceed after task execution begins"
                ),
            },
        )

    calendar = (
        db.query(DBResourceCalendarVersion)
        .filter(
            DBResourceCalendarVersion.id == proposal.target_calendar_version_id,
            DBResourceCalendarVersion.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if (
        calendar is None
        or not calendar.active
        or calendar.evidence_status != CalendarEvidenceStatus.REVIEWED.value
        or calendar.content_hash != proposal.target_calendar_content_hash
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_calendar_stale",
                "message": "Target calendar is no longer the exact active reviewed version",
            },
        )
    assert_approved_source_plan(
        db,
        household_id=household_id,
        source_plan_id=source.source_plan_id,
        source_plan_version=source.source_plan_version,
    )

    occurrence_set, source_request, source_response = _parse_source_provenance(
        source
    )
    _assert_occurrence_household(occurrence_set, household_id)
    repair_request, repair_result = _parse_proposal_payloads(proposal)
    if (
        repair_request.previous_request.model_dump(mode="json")
        != source_request.model_dump(mode="json")
        or repair_request.previous_response.model_dump(mode="json")
        != source_response.model_dump(mode="json")
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_previous_schedule_mismatch",
                "message": "Repair request previous schedule differs from its source",
            },
        )
    _assert_schedule_matches_calendar(db, calendar, repair_request.revised_request)

    replay_envelope = RepairedPreparationScheduleReplay(
        repair_request=repair_request,
        expected_result=repair_result,
        expected_repair_request_hash=proposal.repair_request_hash,
        expected_repair_result_hash=proposal.repair_result_hash,
        expected_revised_request_hash=proposal.revised_request_hash,
        expected_response_hash=proposal.repaired_response_hash,
    )
    try:
        replay = replay_preparation_schedule(
            method=PreparationScheduleDerivationMethod.REPAIR,
            repair=replay_envelope,
        )
    except PreparationScheduleReplayError as exc:
        raise HTTPException(status_code=409, detail=exc.as_dict()) from exc

    schedule_create = PersistedScheduleCreateRequest.model_validate(
        {
            "calendar_version_id": calendar.id,
            "source_plan_id": source.source_plan_id,
            "source_plan_version": source.source_plan_version,
            "occurrence_set": occurrence_set.model_dump(mode="json"),
            "profile_versions": dict(source.profile_versions or {}),
            "schedule_request": repair_request.revised_request.model_dump(mode="json"),
            "schedule_response": replay.replayed_response.model_dump(mode="json"),
            "notes": payload.reason,
            "idempotency_key": (
                f"repair-accepted-draft:{proposal.id}:{payload.idempotency_key}"
            ),
        }
    )
    request_payload = repair_request.revised_request.model_dump(mode="json")
    request_hash = _canonical_hash(request_payload)
    if request_hash != proposal.revised_request_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_revised_request_hash_drift",
                "message": "Revised request differs after provenance validation",
            },
        )

    accepted_proposal_version = proposal.version + 1
    base_schedule_hash = _schedule_hash(
        calendar_content_hash=calendar.content_hash,
        source_plan_id=source.source_plan_id,
        source_plan_version=source.source_plan_version,
        occurrence_set_version=schedule_create.occurrence_set_version,
        occurrence_set_hash=schedule_create.occurrence_set_hash,
        profile_versions=schedule_create.profile_versions,
        schedule_request=repair_request.revised_request,
        schedule_response=replay.replayed_response,
    )
    schedule_hash = _repaired_combined_schedule_hash(
        base_schedule_hash=base_schedule_hash,
        proposal=proposal,
        accepted_proposal_version=accepted_proposal_version,
    )
    now = utcnow()
    schedule_event_key = (
        f"repair-accepted-draft-created:{proposal.id}:{payload.idempotency_key}"
    )
    schedule_fingerprint = _canonical_hash(
        {
            "acceptance_request_fingerprint": fingerprint,
            "proposal_id": proposal.id,
            "accepted_proposal_version": accepted_proposal_version,
            "schedule_hash": schedule_hash,
        }
    )
    schedule = DBPersistedPreparationSchedule(
        household_id=household_id,
        calendar_version_id=calendar.id,
        calendar_content_hash=calendar.content_hash,
        source_plan_id=source.source_plan_id,
        source_plan_version=source.source_plan_version,
        occurrence_set_version=schedule_create.occurrence_set_version,
        occurrence_set_hash=schedule_create.occurrence_set_hash,
        occurrence_set_payload=occurrence_set.model_dump(mode="json"),
        profile_versions=dict(sorted(schedule_create.profile_versions.items())),
        schedule_request_payload=request_payload,
        schedule_request_hash=request_hash,
        schedule_payload=replay.replayed_response.model_dump(mode="json"),
        schedule_hash=schedule_hash,
        derivation_method=REPAIR_SCHEDULER_METHOD,
        source_repair_proposal_id=proposal.id,
        source_repair_proposal_version=accepted_proposal_version,
        source_repair_request_hash=proposal.repair_request_hash,
        source_repair_result_hash=proposal.repair_result_hash,
        source_revised_request_hash=proposal.revised_request_hash,
        source_repaired_response_hash=proposal.repaired_response_hash,
        status=PreparationScheduleStatus.DRAFT.value,
        version=1,
        notes=payload.reason,
        created_by_user_id=actor_user_id,
        approved_by_user_id=None,
        approved_at=None,
        invalidated_at=None,
        invalidation_reason=None,
        creation_idempotency_key=schedule_create.idempotency_key,
        creation_request_fingerprint=schedule_fingerprint,
        created_at=now,
        updated_at=now,
    )
    db.add(schedule)
    db.flush()
    _append_event(
        db,
        schedule=schedule,
        event_type=PreparationScheduleEventType.CREATED,
        actor_user_id=actor_user_id,
        from_status=None,
        to_status=PreparationScheduleStatus.DRAFT.value,
        reason="New draft created from explicitly accepted repair proposal",
        metadata={
            "derivation_method": REPAIR_SCHEDULER_METHOD,
            "source_repair_proposal_id": proposal.id,
            "source_repair_proposal_version": accepted_proposal_version,
            "source_schedule_id": source.id,
            "source_schedule_version": source.version,
            "source_schedule_hash": source.schedule_hash,
            "target_calendar_version_id": calendar.id,
            "target_calendar_content_hash": calendar.content_hash,
            "repair_request_hash": proposal.repair_request_hash,
            "repair_result_hash": proposal.repair_result_hash,
            "revised_request_hash": proposal.revised_request_hash,
            "repaired_response_hash": proposal.repaired_response_hash,
            "schedule_hash": schedule_hash,
            "approval_performed": False,
            "execution_performed": False,
        },
        idempotency_key=schedule_event_key,
        request_fingerprint=schedule_fingerprint,
        created_at=now,
    )

    before = proposal.version
    proposal.status = PreparationRepairProposalStatus.ACCEPTED.value
    proposal.version = accepted_proposal_version
    proposal.updated_at = now
    db.add(proposal)
    acceptance = DBPreparationRepairProposalAcceptance(
        household_id=household_id,
        proposal_id=proposal.id,
        proposal_version_before=before,
        proposal_version_after=accepted_proposal_version,
        source_schedule_id=source.id,
        source_schedule_version=source.version,
        created_schedule_id=schedule.id,
        created_schedule_version=1,
        derivation_method=REPAIR_SCHEDULER_METHOD,
        source_schedule_hash=source.schedule_hash,
        source_schedule_request_hash=source.schedule_request_hash,
        target_calendar_content_hash=calendar.content_hash,
        repair_request_hash=proposal.repair_request_hash,
        repair_result_hash=proposal.repair_result_hash,
        revised_request_hash=proposal.revised_request_hash,
        repaired_response_hash=proposal.repaired_response_hash,
        acknowledged_task_ids=payload.acknowledged_task_ids,
        reason=payload.reason,
        actor_user_id=actor_user_id,
        acceptance_metadata=payload.metadata,
        idempotency_key=payload.idempotency_key,
        request_fingerprint=fingerprint,
        created_at=now,
    )
    db.add(acceptance)
    db.flush()
    _event(
        db,
        proposal=proposal,
        event_type=PreparationRepairProposalEventType.ACCEPTED,
        actor_user_id=actor_user_id,
        from_status=PreparationRepairProposalStatus.PROPOSED.value,
        to_status=PreparationRepairProposalStatus.ACCEPTED.value,
        reason=payload.reason,
        metadata={
            **payload.metadata,
            "acceptance_id": acceptance.id,
            "created_schedule_id": schedule.id,
            "created_schedule_version": 1,
            "created_schedule_status": "draft",
            "created_schedule_hash": schedule_hash,
            "derivation_method": REPAIR_SCHEDULER_METHOD,
            "acknowledged_task_ids": payload.acknowledged_task_ids,
            "schedule_persistence_performed": True,
            "approval_performed": False,
            "execution_performed": False,
        },
        proposal_version_before=before,
        proposal_version_after=accepted_proposal_version,
        idempotency_key=payload.idempotency_key,
        request_fingerprint=fingerprint,
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        concurrent = (
            db.query(DBPreparationRepairProposalAcceptance)
            .filter(
                DBPreparationRepairProposalAcceptance.household_id == household_id,
                DBPreparationRepairProposalAcceptance.idempotency_key
                == payload.idempotency_key,
            )
            .first()
        )
        if concurrent is not None:
            if (
                concurrent.proposal_id != proposal_id
                or concurrent.request_fingerprint != fingerprint
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "repair_acceptance_idempotency_conflict",
                        "message": (
                            "Repair acceptance key conflicted with concurrent content"
                        ),
                    },
                ) from exc
            concurrent_proposal = db.get(
                DBPreparationRepairProposal,
                concurrent.proposal_id,
            )
            if concurrent_proposal is None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "repair_acceptance_concurrent_state_invalid",
                        "message": "Concurrent acceptance lacks its proposal",
                    },
                ) from exc
            return _accepted_draft_view(
                db,
                proposal=concurrent_proposal,
                acceptance=concurrent,
            )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_conflict",
                "message": "Repair acceptance conflicted with concurrent state",
            },
        ) from exc

    db.refresh(schedule)
    db.refresh(proposal)
    db.refresh(acceptance)
    return _accepted_draft_view(
        db,
        proposal=proposal,
        acceptance=acceptance,
    )


__all__ = ["accept_repair_proposal"]
