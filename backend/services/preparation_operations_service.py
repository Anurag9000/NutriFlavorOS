"""Transactional household preparation calendar and schedule services.

Every persisted schedule is bound to an immutable reviewed resource calendar,
a verified occurrence-set document, the complete deterministic scheduler
request, and the exact replayed response. Approval fails closed when any of
those inputs are missing or have drifted.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Iterable, List

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import DBHousehold, DBMealPlan
from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    HouseholdResourceView,
    PersistedPreparationScheduleView,
    PreparationOccurrenceSetDocument,
    PreparationScheduleEventType,
    PreparationScheduleEventView,
    PreparationScheduleStatus,
    ResourceCalendarVersionCreate,
    ResourceCalendarVersionView,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.preparation_operations_models import (
    DBHouseholdPreparationResource,
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)


ACTIVE_SCHEDULE_STATUSES = {
    PreparationScheduleStatus.DRAFT.value,
    PreparationScheduleStatus.APPROVED.value,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalize_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_review_timestamp",
                "message": "reviewed_at must be an ISO-8601 timestamp",
            },
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _lock_household(db: Session, household_id: str) -> DBHousehold:
    household = (
        db.query(DBHousehold)
        .filter(DBHousehold.id == household_id)
        .with_for_update()
        .first()
    )
    if household is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"nutriflavos:preparation-operations:{household_id}"},
        )
    return household


def _calendar_content(payload: ResourceCalendarVersionCreate) -> dict:
    return {
        "calendar_version": payload.calendar_version,
        "horizon_minutes": payload.horizon_minutes,
        "timezone": payload.timezone,
        "resources": [
            value.model_dump(mode="json")
            for value in sorted(payload.resources, key=lambda item: item.resource_id)
        ],
        "evidence_status": payload.evidence_status.value,
        "reviewed_at": payload.reviewed_at,
        "reviewed_by": payload.reviewed_by,
        "notes": payload.notes,
    }


def _calendar_request_fingerprint(
    payload: ResourceCalendarVersionCreate,
    actor_user_id: str,
) -> str:
    return _canonical_hash(
        {
            "actor_user_id": actor_user_id,
            "content": _calendar_content(payload),
            "activate": payload.activate,
        }
    )


def _schedule_request_fingerprint(
    payload: PersistedScheduleCreateRequest,
    actor_user_id: str,
) -> str:
    # Keep the established fingerprint shape so exact legacy retries can be
    # recognized while separately persisting the complete occurrence document.
    return _canonical_hash(
        {
            "actor_user_id": actor_user_id,
            "calendar_version_id": payload.calendar_version_id,
            "source_plan_id": payload.source_plan_id,
            "source_plan_version": payload.source_plan_version,
            "occurrence_set_version": payload.occurrence_set_version,
            "occurrence_set_hash": payload.occurrence_set_hash,
            "profile_versions": dict(sorted(payload.profile_versions.items())),
            "schedule_request": payload.schedule_request.model_dump(mode="json"),
            "schedule_response": payload.schedule_response.model_dump(mode="json"),
            "notes": payload.notes,
        }
    )


def _transition_fingerprint(
    schedule_id: int,
    event_type: PreparationScheduleEventType,
    payload: ScheduleStateTransitionRequest,
    actor_user_id: str,
) -> str:
    return _canonical_hash(
        {
            "schedule_id": schedule_id,
            "event_type": event_type.value,
            "expected_version": payload.expected_version,
            "reason": payload.reason,
            "metadata": payload.metadata,
            "actor_user_id": actor_user_id,
        }
    )


def _schedule_hash(
    *,
    calendar_content_hash: str,
    source_plan_id: int | None,
    source_plan_version: int | None,
    occurrence_set_version: str,
    occurrence_set_hash: str,
    profile_versions: dict[str, str],
    schedule_request: PreparationScheduleRequest,
    schedule_response: PreparationScheduleResponse,
) -> str:
    return _canonical_hash(
        {
            "calendar_content_hash": calendar_content_hash,
            "source_plan_id": source_plan_id,
            "source_plan_version": source_plan_version,
            "occurrence_set_version": occurrence_set_version,
            "occurrence_set_hash": occurrence_set_hash,
            "profile_versions": dict(sorted(profile_versions.items())),
            "schedule_request": schedule_request.model_dump(mode="json"),
            "schedule_response": schedule_response.model_dump(mode="json"),
        }
    )


def _calendar_resources(
    db: Session,
    calendar_id: int,
) -> List[DBHouseholdPreparationResource]:
    return (
        db.query(DBHouseholdPreparationResource)
        .filter(
            DBHouseholdPreparationResource.calendar_version_id == calendar_id
        )
        .order_by(DBHouseholdPreparationResource.resource_id)
        .all()
    )


def _resource_view(value: DBHouseholdPreparationResource) -> HouseholdResourceView:
    return HouseholdResourceView(
        id=value.id,
        calendar_version_id=value.calendar_version_id,
        resource_id=value.resource_id,
        label=value.label,
        capacity=value.capacity,
        resource_kind=value.resource_kind,
        availability_windows=value.availability_windows,
        metadata=dict(value.resource_metadata or {}),
    )


def _calendar_view(
    db: Session,
    value: DBResourceCalendarVersion,
) -> ResourceCalendarVersionView:
    return ResourceCalendarVersionView(
        id=value.id,
        household_id=value.household_id,
        calendar_version=value.calendar_version,
        horizon_minutes=value.horizon_minutes,
        timezone=value.timezone,
        evidence_status=CalendarEvidenceStatus(value.evidence_status),
        reviewed_at=value.reviewed_at.isoformat() if value.reviewed_at else None,
        reviewed_by=value.reviewed_by,
        notes=value.notes,
        content_hash=value.content_hash,
        supersedes_calendar_id=value.supersedes_calendar_id,
        active=bool(value.active),
        created_by_user_id=value.created_by_user_id,
        created_at=value.created_at.isoformat(),
        updated_at=value.updated_at.isoformat(),
        resources=[
            _resource_view(resource)
            for resource in _calendar_resources(db, value.id)
        ],
    )


def _parse_persisted_provenance(
    value: DBPersistedPreparationSchedule,
) -> tuple[
    PreparationOccurrenceSetDocument | None,
    PreparationScheduleRequest | None,
    PreparationScheduleResponse,
    str,
]:
    try:
        occurrence_set = (
            PreparationOccurrenceSetDocument.model_validate(
                value.occurrence_set_payload
            )
            if value.occurrence_set_payload is not None
            else None
        )
        request = (
            PreparationScheduleRequest.model_validate(
                value.schedule_request_payload
            )
            if value.schedule_request_payload is not None
            else None
        )
        response = PreparationScheduleResponse.model_validate(
            value.schedule_payload
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "persisted_schedule_provenance_invalid",
                "message": "Persisted preparation provenance no longer validates",
            },
        ) from exc

    if request is None:
        replay_status = "legacy_request_missing"
    elif occurrence_set is None:
        replay_status = "legacy_occurrence_set_missing"
    else:
        replay_status = "replayable"
    return occurrence_set, request, response, replay_status


def _schedule_view(
    value: DBPersistedPreparationSchedule,
) -> PersistedPreparationScheduleView:
    occurrence_set, request, response, replay_status = (
        _parse_persisted_provenance(value)
    )
    return PersistedPreparationScheduleView(
        id=value.id,
        household_id=value.household_id,
        calendar_version_id=value.calendar_version_id,
        calendar_content_hash=value.calendar_content_hash,
        source_plan_id=value.source_plan_id,
        source_plan_version=value.source_plan_version,
        occurrence_set_version=value.occurrence_set_version,
        occurrence_set_hash=value.occurrence_set_hash,
        occurrence_set=occurrence_set,
        profile_versions=dict(value.profile_versions or {}),
        schedule_request=request,
        schedule_request_hash=value.schedule_request_hash,
        replay_status=replay_status,
        schedule=response,
        schedule_hash=value.schedule_hash,
        status=PreparationScheduleStatus(value.status),
        version=value.version,
        notes=value.notes,
        created_by_user_id=value.created_by_user_id,
        approved_by_user_id=value.approved_by_user_id,
        approved_at=value.approved_at.isoformat() if value.approved_at else None,
        invalidated_at=(
            value.invalidated_at.isoformat() if value.invalidated_at else None
        ),
        invalidation_reason=value.invalidation_reason,
        created_at=value.created_at.isoformat(),
        updated_at=value.updated_at.isoformat(),
    )


def _event_view(value: DBPreparationScheduleEvent) -> PreparationScheduleEventView:
    return PreparationScheduleEventView(
        id=value.id,
        schedule_id=value.schedule_id,
        household_id=value.household_id,
        event_type=PreparationScheduleEventType(value.event_type),
        actor_user_id=value.actor_user_id,
        from_status=(
            PreparationScheduleStatus(value.from_status)
            if value.from_status
            else None
        ),
        to_status=PreparationScheduleStatus(value.to_status),
        reason=value.reason,
        metadata=dict(value.event_metadata or {}),
        idempotency_key=value.idempotency_key,
        request_fingerprint=value.request_fingerprint,
        created_at=value.created_at.isoformat(),
    )


def _calendar_request_resources(
    db: Session,
    calendar: DBResourceCalendarVersion,
) -> List[PreparationResource]:
    return [
        PreparationResource.model_validate(
            {
                "resource_id": value.resource_id,
                "label": value.label,
                "capacity": value.capacity,
                "availability_windows": value.availability_windows,
            }
        )
        for value in _calendar_resources(db, calendar.id)
    ]


def _assert_schedule_matches_calendar(
    db: Session,
    calendar: DBResourceCalendarVersion,
    request: PreparationScheduleRequest,
) -> None:
    if request.horizon_minutes != calendar.horizon_minutes:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "calendar_horizon_mismatch",
                "message": (
                    "Schedule horizon must equal the selected calendar horizon"
                ),
            },
        )
    expected = [
        value.model_dump(mode="json")
        for value in _calendar_request_resources(db, calendar)
    ]
    observed = [
        value.model_dump(mode="json")
        for value in sorted(
            request.resources,
            key=lambda item: item.resource_id,
        )
    ]
    if observed != expected:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "calendar_resource_mismatch",
                "message": (
                    "Schedule resources must exactly match the selected "
                    "immutable calendar version"
                ),
            },
        )


def _assert_source_plan(
    db: Session,
    household_id: str,
    source_plan_id: int | None,
    source_plan_version: int | None,
) -> None:
    if source_plan_id is None:
        return
    plan = db.get(DBMealPlan, source_plan_id)
    if (
        plan is None
        or plan.household_id != household_id
        or plan.version != source_plan_version
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_plan_version_mismatch",
                "message": (
                    "The source household plan is missing or its version changed"
                ),
            },
        )


def _assert_occurrence_household(
    occurrence_set: PreparationOccurrenceSetDocument,
    household_id: str,
) -> None:
    if occurrence_set.household_id != household_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "occurrence_set_household_mismatch",
                "message": (
                    "Occurrence set household_id must match the route household"
                ),
            },
        )


def _append_event(
    db: Session,
    *,
    schedule: DBPersistedPreparationSchedule,
    event_type: PreparationScheduleEventType,
    actor_user_id: str,
    from_status: str | None,
    to_status: str,
    reason: str,
    metadata: dict,
    idempotency_key: str,
    request_fingerprint: str,
    created_at: datetime,
) -> DBPreparationScheduleEvent:
    event = DBPreparationScheduleEvent(
        schedule_id=schedule.id,
        household_id=schedule.household_id,
        event_type=event_type.value,
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        event_metadata=metadata,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        created_at=created_at,
    )
    db.add(event)
    db.flush()
    return event


def _invalidate_schedules_for_calendar(
    db: Session,
    *,
    calendar_id: int,
    replacement_calendar_id: int,
    actor_user_id: str,
    now: datetime,
) -> int:
    schedules = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.calendar_version_id == calendar_id,
            DBPersistedPreparationSchedule.status.in_(ACTIVE_SCHEDULE_STATUSES),
        )
        .with_for_update()
        .all()
    )
    for schedule in schedules:
        previous = schedule.status
        schedule.status = PreparationScheduleStatus.INVALIDATED.value
        schedule.version += 1
        schedule.invalidated_at = now
        schedule.invalidation_reason = (
            "Resource calendar superseded by calendar record "
            f"{replacement_calendar_id}"
        )
        schedule.updated_at = now
        db.add(schedule)
        event_key = (
            f"calendar-supersede:{replacement_calendar_id}:"
            f"schedule:{schedule.id}"
        )
        fingerprint = _canonical_hash(
            {
                "schedule_id": schedule.id,
                "replacement_calendar_id": replacement_calendar_id,
                "actor_user_id": actor_user_id,
                "from_status": previous,
            }
        )
        _append_event(
            db,
            schedule=schedule,
            event_type=PreparationScheduleEventType.INVALIDATED,
            actor_user_id=actor_user_id,
            from_status=previous,
            to_status=PreparationScheduleStatus.INVALIDATED.value,
            reason=schedule.invalidation_reason,
            metadata={
                "superseded_calendar_id": calendar_id,
                "replacement_calendar_id": replacement_calendar_id,
            },
            idempotency_key=event_key,
            request_fingerprint=fingerprint,
            created_at=now,
        )
    return len(schedules)


def register_resource_calendar(
    db: Session,
    *,
    household_id: str,
    actor_user_id: str,
    payload: ResourceCalendarVersionCreate,
) -> ResourceCalendarVersionView:
    _lock_household(db, household_id)
    fingerprint = _calendar_request_fingerprint(payload, actor_user_id)
    existing_idempotent = (
        db.query(DBResourceCalendarVersion)
        .filter(
            DBResourceCalendarVersion.household_id == household_id,
            DBResourceCalendarVersion.idempotency_key == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing_idempotent is not None:
        if existing_idempotent.request_fingerprint != fingerprint:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "calendar_idempotency_conflict",
                    "message": (
                        "Calendar idempotency key was reused with different content"
                    ),
                },
            )
        return _calendar_view(db, existing_idempotent)

    content_hash = _canonical_hash(_calendar_content(payload))
    same_version = (
        db.query(DBResourceCalendarVersion)
        .filter(
            DBResourceCalendarVersion.household_id == household_id,
            DBResourceCalendarVersion.calendar_version
            == payload.calendar_version,
        )
        .with_for_update()
        .first()
    )
    if same_version is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_version_conflict",
                "message": (
                    "Calendar version already exists under a different request key"
                ),
            },
        )

    predecessor = None
    if payload.activate:
        predecessor = (
            db.query(DBResourceCalendarVersion)
            .filter(
                DBResourceCalendarVersion.household_id == household_id,
                DBResourceCalendarVersion.evidence_status
                == CalendarEvidenceStatus.REVIEWED.value,
                DBResourceCalendarVersion.active.is_(True),
            )
            .with_for_update()
            .first()
        )

    now = utcnow()
    if predecessor is not None:
        predecessor.active = False
        predecessor.updated_at = now
        db.add(predecessor)
        db.flush()

    calendar = DBResourceCalendarVersion(
        household_id=household_id,
        calendar_version=payload.calendar_version,
        horizon_minutes=payload.horizon_minutes,
        timezone=payload.timezone,
        evidence_status=payload.evidence_status.value,
        reviewed_at=_normalize_datetime(payload.reviewed_at),
        reviewed_by=payload.reviewed_by,
        notes=payload.notes,
        content_hash=content_hash,
        supersedes_calendar_id=(predecessor.id if predecessor else None),
        active=payload.activate,
        created_by_user_id=actor_user_id,
        idempotency_key=payload.idempotency_key,
        request_fingerprint=fingerprint,
        created_at=now,
        updated_at=now,
    )
    db.add(calendar)
    db.flush()
    for resource in sorted(payload.resources, key=lambda item: item.resource_id):
        db.add(
            DBHouseholdPreparationResource(
                calendar_version_id=calendar.id,
                resource_id=resource.resource_id,
                label=resource.label,
                capacity=resource.capacity,
                resource_kind=resource.resource_kind,
                availability_windows=[
                    value.model_dump(mode="json")
                    for value in resource.availability_windows
                ],
                resource_metadata=resource.metadata,
            )
        )
    db.flush()
    if predecessor is not None:
        _invalidate_schedules_for_calendar(
            db,
            calendar_id=predecessor.id,
            replacement_calendar_id=calendar.id,
            actor_user_id=actor_user_id,
            now=now,
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_registration_conflict",
                "message": (
                    "Calendar registration conflicted with concurrent state"
                ),
            },
        ) from exc
    db.refresh(calendar)
    return _calendar_view(db, calendar)


def list_resource_calendars(
    db: Session,
    *,
    household_id: str,
    active_only: bool = False,
) -> List[ResourceCalendarVersionView]:
    query = db.query(DBResourceCalendarVersion).filter(
        DBResourceCalendarVersion.household_id == household_id
    )
    if active_only:
        query = query.filter(DBResourceCalendarVersion.active.is_(True))
    rows = query.order_by(
        DBResourceCalendarVersion.created_at.desc(),
        DBResourceCalendarVersion.id.desc(),
    ).all()
    return [_calendar_view(db, value) for value in rows]


def get_resource_calendar(
    db: Session,
    *,
    household_id: str,
    calendar_id: int,
) -> ResourceCalendarVersionView:
    value = (
        db.query(DBResourceCalendarVersion)
        .filter(
            DBResourceCalendarVersion.id == calendar_id,
            DBResourceCalendarVersion.household_id == household_id,
        )
        .first()
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return _calendar_view(db, value)


def _backfill_replay_provenance(
    db: Session,
    existing: DBPersistedPreparationSchedule,
    payload: PersistedScheduleCreateRequest,
) -> None:
    changed = False
    request_payload = payload.schedule_request.model_dump(mode="json")
    request_hash = _canonical_hash(request_payload)
    occurrence_payload = payload.occurrence_set.model_dump(mode="json")

    if existing.occurrence_set_payload is None:
        if (
            existing.occurrence_set_version != payload.occurrence_set_version
            or existing.occurrence_set_hash != payload.occurrence_set_hash
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "legacy_occurrence_provenance_conflict",
                    "message": (
                        "Legacy occurrence fingerprint differs from retry content"
                    ),
                },
            )
        existing.occurrence_set_payload = occurrence_payload
        changed = True
    elif _canonical_hash(existing.occurrence_set_payload) != payload.occurrence_set_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "persisted_occurrence_hash_mismatch",
                "message": "Persisted occurrence document does not match its hash",
            },
        )

    if existing.schedule_request_payload is None:
        existing.schedule_request_payload = request_payload
        existing.schedule_request_hash = request_hash
        changed = True
    elif (
        existing.schedule_request_hash != request_hash
        or _canonical_hash(existing.schedule_request_payload) != request_hash
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "persisted_schedule_request_hash_mismatch",
                "message": "Persisted schedule request does not match its hash",
            },
        )

    if changed:
        existing.updated_at = utcnow()
        db.add(existing)
        db.commit()
        db.refresh(existing)


def create_persisted_schedule(
    db: Session,
    *,
    household_id: str,
    actor_user_id: str,
    payload: PersistedScheduleCreateRequest,
) -> PersistedPreparationScheduleView:
    _lock_household(db, household_id)
    _assert_occurrence_household(payload.occurrence_set, household_id)
    fingerprint = _schedule_request_fingerprint(payload, actor_user_id)
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
                    "message": (
                        "Schedule idempotency key was reused with different content"
                    ),
                },
            )
        _backfill_replay_provenance(db, existing, payload)
        return _schedule_view(existing)

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
                "message": (
                    "Schedules may be persisted only against the active "
                    "reviewed calendar"
                ),
            },
        )

    _assert_schedule_matches_calendar(db, calendar, payload.schedule_request)
    _assert_source_plan(
        db,
        household_id,
        payload.source_plan_id,
        payload.source_plan_version,
    )
    replay = build_preparation_schedule(payload.schedule_request)
    if (
        replay.model_dump(mode="json")
        != payload.schedule_response.model_dump(mode="json")
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "schedule_replay_mismatch",
                "message": (
                    "Submitted schedule response does not match deterministic "
                    "server replay"
                ),
            },
        )
    if replay.unscheduled:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "incomplete_schedule",
                "message": (
                    "Schedules with unresolved tasks cannot be persisted"
                ),
            },
        )

    occurrence_payload = payload.occurrence_set.model_dump(mode="json")
    request_payload = payload.schedule_request.model_dump(mode="json")
    request_hash = _canonical_hash(request_payload)
    schedule_hash = _schedule_hash(
        calendar_content_hash=calendar.content_hash,
        source_plan_id=payload.source_plan_id,
        source_plan_version=payload.source_plan_version,
        occurrence_set_version=payload.occurrence_set_version,
        occurrence_set_hash=payload.occurrence_set_hash,
        profile_versions=payload.profile_versions,
        schedule_request=payload.schedule_request,
        schedule_response=replay,
    )
    now = utcnow()
    schedule = DBPersistedPreparationSchedule(
        household_id=household_id,
        calendar_version_id=calendar.id,
        calendar_content_hash=calendar.content_hash,
        source_plan_id=payload.source_plan_id,
        source_plan_version=payload.source_plan_version,
        occurrence_set_version=payload.occurrence_set_version,
        occurrence_set_hash=payload.occurrence_set_hash,
        occurrence_set_payload=occurrence_payload,
        profile_versions=dict(sorted(payload.profile_versions.items())),
        schedule_request_payload=request_payload,
        schedule_request_hash=request_hash,
        schedule_payload=replay.model_dump(mode="json"),
        schedule_hash=schedule_hash,
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
    db.add(schedule)
    db.flush()
    _append_event(
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
            "occurrence_set_hash": payload.occurrence_set_hash,
            "schedule_request_hash": request_hash,
            "schedule_hash": schedule_hash,
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
                "message": (
                    "Schedule creation conflicted with concurrent state"
                ),
            },
        ) from exc
    db.refresh(schedule)
    return _schedule_view(schedule)


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
    return [_schedule_view(value) for value in rows]


def get_persisted_schedule(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> PersistedPreparationScheduleView:
    value = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return _schedule_view(value)


def _validate_approval_replay(
    db: Session,
    *,
    household_id: str,
    schedule: DBPersistedPreparationSchedule,
    calendar: DBResourceCalendarVersion,
) -> None:
    if schedule.schedule_request_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_replay_input_missing",
                "message": (
                    "Legacy schedule lacks the deterministic request required "
                    "for approval"
                ),
            },
        )
    if schedule.occurrence_set_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_occurrence_set_missing",
                "message": (
                    "Legacy schedule lacks the verified occurrence document "
                    "required for approval"
                ),
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
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_provenance_validation_failed",
                "message": (
                    "Persisted occurrence, profile, request, and response "
                    "provenance no longer agree"
                ),
            },
        ) from exc

    _assert_occurrence_household(occurrence_set, household_id)
    _assert_schedule_matches_calendar(db, calendar, request)
    _assert_source_plan(
        db,
        household_id,
        schedule.source_plan_id,
        schedule.source_plan_version,
    )

    request_hash = _canonical_hash(request.model_dump(mode="json"))
    if request_hash != schedule.schedule_request_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_request_hash_mismatch",
                "message": "Persisted scheduler request hash no longer matches",
            },
        )
    if verified.occurrence_set_hash != schedule.occurrence_set_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "occurrence_set_hash_mismatch",
                "message": "Persisted occurrence document hash no longer matches",
            },
        )

    replay = build_preparation_schedule(request)
    if replay.model_dump(mode="json") != response.model_dump(mode="json"):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_approval_replay_mismatch",
                "message": (
                    "Persisted response differs from deterministic approval replay"
                ),
            },
        )
    expected_schedule_hash = _schedule_hash(
        calendar_content_hash=calendar.content_hash,
        source_plan_id=schedule.source_plan_id,
        source_plan_version=schedule.source_plan_version,
        occurrence_set_version=verified.occurrence_set_version,
        occurrence_set_hash=verified.occurrence_set_hash,
        profile_versions=verified.profile_versions,
        schedule_request=request,
        schedule_response=replay,
    )
    if expected_schedule_hash != schedule.schedule_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_hash_mismatch",
                "message": "Combined persisted schedule hash no longer matches",
            },
        )


def transition_schedule(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    event_type: PreparationScheduleEventType,
    payload: ScheduleStateTransitionRequest,
) -> PersistedPreparationScheduleView:
    _lock_household(db, household_id)
    fingerprint = _transition_fingerprint(
        schedule_id,
        event_type,
        payload,
        actor_user_id,
    )
    existing_event = (
        db.query(DBPreparationScheduleEvent)
        .filter(
            DBPreparationScheduleEvent.household_id == household_id,
            DBPreparationScheduleEvent.idempotency_key
            == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing_event is not None:
        if (
            existing_event.schedule_id != schedule_id
            or existing_event.event_type != event_type.value
            or existing_event.request_fingerprint != fingerprint
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "schedule_event_idempotency_conflict",
                    "message": (
                        "Schedule event idempotency key was reused with a "
                        "different request"
                    ),
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
                "message": (
                    "Schedule version changed; reload before mutating it"
                ),
                "current_version": schedule.version,
            },
        )

    current = PreparationScheduleStatus(schedule.status)
    allowed = {
        PreparationScheduleEventType.APPROVED: {
            PreparationScheduleStatus.DRAFT,
        },
        PreparationScheduleEventType.COMPLETED: {
            PreparationScheduleStatus.APPROVED,
        },
        PreparationScheduleEventType.CANCELLED: {
            PreparationScheduleStatus.DRAFT,
            PreparationScheduleStatus.APPROVED,
        },
        PreparationScheduleEventType.INVALIDATED: {
            PreparationScheduleStatus.DRAFT,
            PreparationScheduleStatus.APPROVED,
        },
    }
    if event_type not in allowed or current not in allowed[event_type]:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_schedule_transition",
                "message": (
                    f"Cannot apply {event_type.value} to {current.value} schedule"
                ),
            },
        )

    calendar = db.get(DBResourceCalendarVersion, schedule.calendar_version_id)
    if event_type == PreparationScheduleEventType.APPROVED:
        if (
            calendar is None
            or not calendar.active
            or calendar.content_hash != schedule.calendar_content_hash
            or calendar.evidence_status
            != CalendarEvidenceStatus.REVIEWED.value
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "schedule_calendar_stale",
                    "message": (
                        "Schedule calendar is no longer the active reviewed version"
                    ),
                },
            )
        _validate_approval_replay(
            db,
            household_id=household_id,
            schedule=schedule,
            calendar=calendar,
        )

    target = {
        PreparationScheduleEventType.APPROVED: (
            PreparationScheduleStatus.APPROVED
        ),
        PreparationScheduleEventType.COMPLETED: (
            PreparationScheduleStatus.COMPLETED
        ),
        PreparationScheduleEventType.CANCELLED: (
            PreparationScheduleStatus.CANCELLED
        ),
        PreparationScheduleEventType.INVALIDATED: (
            PreparationScheduleStatus.INVALIDATED
        ),
    }[event_type]
    now = utcnow()
    schedule.status = target.value
    schedule.version += 1
    schedule.updated_at = now
    if target == PreparationScheduleStatus.APPROVED:
        schedule.approved_by_user_id = actor_user_id
        schedule.approved_at = now
    if target == PreparationScheduleStatus.INVALIDATED:
        schedule.invalidated_at = now
        schedule.invalidation_reason = payload.reason
    db.add(schedule)
    _append_event(
        db,
        schedule=schedule,
        event_type=event_type,
        actor_user_id=actor_user_id,
        from_status=current.value,
        to_status=target.value,
        reason=payload.reason,
        metadata=payload.metadata,
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
                "message": (
                    "Schedule transition conflicted with concurrent state"
                ),
            },
        ) from exc
    db.refresh(schedule)
    return _schedule_view(schedule)


def list_schedule_events(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> List[PreparationScheduleEventView]:
    exists = (
        db.query(DBPersistedPreparationSchedule.id)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    rows = (
        db.query(DBPreparationScheduleEvent)
        .filter(
            DBPreparationScheduleEvent.schedule_id == schedule_id,
            DBPreparationScheduleEvent.household_id == household_id,
        )
        .order_by(
            DBPreparationScheduleEvent.created_at,
            DBPreparationScheduleEvent.id,
        )
        .all()
    )
    return [_event_view(value) for value in rows]
