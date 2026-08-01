"""Replay-aware persistence wrappers for household preparation operations.

Migration 0010 stores the complete deterministic request alongside the response.
Rows created under 0009 remain readable, but approval fails closed because their
request cannot be reconstructed from the response alone.
"""

from __future__ import annotations

from typing import Iterable, List

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    PersistedPreparationScheduleView,
    PreparationScheduleEventType,
    PreparationScheduleStatus,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBResourceCalendarVersion,
)
from backend.services import preparation_operations_service as base


def _request_payload(value: PreparationScheduleRequest) -> dict:
    return value.model_dump(mode="json")


def _request_hash(value: PreparationScheduleRequest) -> str:
    return base._canonical_hash(_request_payload(value))


def _combined_schedule_hash(
    row: DBPersistedPreparationSchedule,
    request_payload: dict,
    response_payload: dict,
) -> str:
    return base._canonical_hash(
        {
            "calendar_content_hash": row.calendar_content_hash,
            "source_plan_id": row.source_plan_id,
            "source_plan_version": row.source_plan_version,
            "occurrence_set_version": row.occurrence_set_version,
            "occurrence_set_hash": row.occurrence_set_hash,
            "profile_versions": dict(sorted((row.profile_versions or {}).items())),
            "schedule_request": request_payload,
            "schedule_response": response_payload,
        }
    )


def _integrity_error(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": code, "message": message})


def _enriched_view(
    row: DBPersistedPreparationSchedule,
) -> PersistedPreparationScheduleView:
    value = base._schedule_view(row).model_dump(mode="json")
    if row.schedule_request_payload is None or row.schedule_request_hash is None:
        value.update(
            {
                "schedule_request": None,
                "schedule_request_hash": None,
                "replay_status": "legacy_request_missing",
            }
        )
    else:
        try:
            request = PreparationScheduleRequest.model_validate(
                row.schedule_request_payload
            )
        except ValidationError as exc:
            raise _integrity_error(
                "stored_schedule_request_invalid",
                "Stored schedule request no longer satisfies the preparation contract",
            ) from exc
        value.update(
            {
                "schedule_request": request.model_dump(mode="json"),
                "schedule_request_hash": row.schedule_request_hash,
                "replay_status": "replayable",
            }
        )
    return PersistedPreparationScheduleView.model_validate(value)


def validate_persisted_schedule_integrity(
    db: Session,
    row: DBPersistedPreparationSchedule,
) -> tuple[PreparationScheduleRequest, PreparationScheduleResponse]:
    if row.schedule_request_payload is None or row.schedule_request_hash is None:
        raise _integrity_error(
            "schedule_request_provenance_missing",
            "This legacy schedule predates replay-input persistence and cannot be approved; recreate it against the current calendar",
        )
    try:
        request = PreparationScheduleRequest.model_validate(
            row.schedule_request_payload
        )
        response = PreparationScheduleResponse.model_validate(row.schedule_payload)
    except ValidationError as exc:
        raise _integrity_error(
            "stored_schedule_payload_invalid",
            "Stored schedule request or response no longer satisfies its contract",
        ) from exc

    observed_request_hash = _request_hash(request)
    if observed_request_hash != row.schedule_request_hash:
        raise _integrity_error(
            "schedule_request_hash_mismatch",
            "Stored schedule request differs from its immutable hash",
        )

    calendar = db.get(DBResourceCalendarVersion, row.calendar_version_id)
    if calendar is None or calendar.household_id != row.household_id:
        raise _integrity_error(
            "schedule_calendar_missing",
            "The immutable resource calendar linked to this schedule is unavailable",
        )
    if calendar.content_hash != row.calendar_content_hash:
        raise _integrity_error(
            "schedule_calendar_hash_mismatch",
            "The linked resource calendar differs from the hash captured by the schedule",
        )
    base._assert_schedule_matches_calendar(db, calendar, request)

    replay = build_preparation_schedule(request)
    replay_payload = replay.model_dump(mode="json")
    response_payload = response.model_dump(mode="json")
    if replay_payload != response_payload:
        raise _integrity_error(
            "stored_schedule_replay_mismatch",
            "Stored schedule response differs from deterministic server replay",
        )
    if replay.unscheduled:
        raise _integrity_error(
            "stored_schedule_incomplete",
            "Stored schedule contains unresolved tasks and cannot be approved",
        )

    observed_schedule_hash = _combined_schedule_hash(
        row,
        request.model_dump(mode="json"),
        replay_payload,
    )
    if observed_schedule_hash != row.schedule_hash:
        raise _integrity_error(
            "schedule_hash_mismatch",
            "Stored schedule provenance differs from its immutable combined hash",
        )
    return request, replay


def create_persisted_schedule(
    db: Session,
    *,
    household_id: str,
    actor_user_id: str,
    payload: PersistedScheduleCreateRequest,
) -> PersistedPreparationScheduleView:
    base._lock_household(db, household_id)
    fingerprint = base._schedule_request_fingerprint(payload, actor_user_id)
    request_payload = _request_payload(payload.schedule_request)
    request_hash = base._canonical_hash(request_payload)

    existing = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.household_id == household_id,
            DBPersistedPreparationSchedule.creation_idempotency_key
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
                    "code": "schedule_idempotency_conflict",
                    "message": "Schedule idempotency key was reused with different content",
                },
            )
        if existing.schedule_request_payload is None:
            # The full creation fingerprint already includes this exact request
            # and response, so a matching retry can safely complete a legacy
            # row's replay provenance without changing its operational state.
            existing.schedule_request_payload = request_payload
            existing.schedule_request_hash = request_hash
            db.add(existing)
            db.commit()
            db.refresh(existing)
        elif (
            existing.schedule_request_hash != request_hash
            or existing.schedule_request_payload != request_payload
        ):
            raise _integrity_error(
                "schedule_idempotent_request_mismatch",
                "Stored replay input conflicts with the matching creation request",
            )
        return _enriched_view(existing)

    calendar = (
        db.query(DBResourceCalendarVersion)
        .filter(
            DBResourceCalendarVersion.id == payload.calendar_version_id,
            DBResourceCalendarVersion.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if (
        calendar is None
        or not calendar.active
        or calendar.evidence_status != CalendarEvidenceStatus.REVIEWED.value
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "active_reviewed_calendar_required",
                "message": "Schedules may be persisted only against the active reviewed calendar",
            },
        )

    base._assert_schedule_matches_calendar(db, calendar, payload.schedule_request)
    base._assert_source_plan(
        db,
        household_id,
        payload.source_plan_id,
        payload.source_plan_version,
    )
    replay = build_preparation_schedule(payload.schedule_request)
    replay_payload = replay.model_dump(mode="json")
    if replay_payload != payload.schedule_response.model_dump(mode="json"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "schedule_replay_mismatch",
                "message": "Submitted schedule response does not match deterministic server replay",
            },
        )
    if replay.unscheduled:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "incomplete_schedule",
                "message": "Schedules with unresolved tasks cannot be persisted",
            },
        )

    now = base.utcnow()
    schedule = DBPersistedPreparationSchedule(
        household_id=household_id,
        calendar_version_id=calendar.id,
        calendar_content_hash=calendar.content_hash,
        source_plan_id=payload.source_plan_id,
        source_plan_version=payload.source_plan_version,
        occurrence_set_version=payload.occurrence_set_version,
        occurrence_set_hash=payload.occurrence_set_hash,
        profile_versions=dict(sorted(payload.profile_versions.items())),
        schedule_request_payload=request_payload,
        schedule_request_hash=request_hash,
        schedule_payload=replay_payload,
        schedule_hash="0" * 64,
        status=PreparationScheduleStatus.DRAFT.value,
        version=1,
        notes=payload.notes,
        created_by_user_id=actor_user_id,
        approved_by_user_id=None,
        approved_at=None,
        invalidated_at=None,
        invalidation_reason=None,
        creation_idempotency_key=payload.idempotency_key,
        creation_request_fingerprint=fingerprint,
        created_at=now,
        updated_at=now,
    )
    schedule.schedule_hash = _combined_schedule_hash(
        schedule,
        request_payload,
        replay_payload,
    )
    db.add(schedule)
    db.flush()
    base._append_event(
        db,
        schedule=schedule,
        event_type=PreparationScheduleEventType.CREATED,
        actor_user_id=actor_user_id,
        from_status=None,
        to_status=PreparationScheduleStatus.DRAFT.value,
        reason="Persisted deterministic preparation schedule created",
        metadata={
            "calendar_version_id": calendar.id,
            "calendar_content_hash": calendar.content_hash,
            "schedule_request_hash": request_hash,
            "schedule_hash": schedule.schedule_hash,
        },
        idempotency_key=f"schedule-created:{schedule.id}",
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
                "code": "schedule_creation_conflict",
                "message": "Schedule creation conflicted with concurrent state",
            },
        ) from exc
    db.refresh(schedule)
    return _enriched_view(schedule)


def list_persisted_schedules(
    db: Session,
    *,
    household_id: str,
    statuses: Iterable[PreparationScheduleStatus] | None = None,
) -> List[PersistedPreparationScheduleView]:
    query = db.query(DBPersistedPreparationSchedule).filter(
        DBPersistedPreparationSchedule.household_id == household_id
    )
    if statuses:
        query = query.filter(
            DBPersistedPreparationSchedule.status.in_(
                [value.value for value in statuses]
            )
        )
    rows = query.order_by(
        DBPersistedPreparationSchedule.created_at.desc(),
        DBPersistedPreparationSchedule.id.desc(),
    ).all()
    return [_enriched_view(value) for value in rows]


def get_persisted_schedule(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> PersistedPreparationScheduleView:
    row = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return _enriched_view(row)


def transition_schedule(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    event_type: PreparationScheduleEventType,
    payload: ScheduleStateTransitionRequest,
) -> PersistedPreparationScheduleView:
    if event_type == PreparationScheduleEventType.APPROVED:
        base._lock_household(db, household_id)
        row = (
            db.query(DBPersistedPreparationSchedule)
            .filter(
                DBPersistedPreparationSchedule.id == schedule_id,
                DBPersistedPreparationSchedule.household_id == household_id,
            )
            .with_for_update()
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Resource not found")
        validate_persisted_schedule_integrity(db, row)

    base.transition_schedule(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload=payload,
    )
    return get_persisted_schedule(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
