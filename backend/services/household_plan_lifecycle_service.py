"""Transactional review lifecycle for persisted household meal plans."""

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

from backend.database import (
    DBHousehold,
    DBMealPlan,
    DBStockReservation,
)
from backend.domain.household_access import ReservationStatus
from backend.domain.household_plan_lifecycle import (
    HouseholdPlanEventType,
    HouseholdPlanEventView,
    HouseholdPlanStatus,
    HouseholdPlanTransitionRequest,
    PersistedHouseholdPlanView,
)
from backend.meal_plan_lifecycle_models import DBHouseholdPlanEvent
from backend.models import PlanResponse


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


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
            {"lock_key": f"nutriflavos:household-plan:{household_id}"},
        )
    return household


def _plan_view(value: DBMealPlan) -> PersistedHouseholdPlanView:
    if value.household_id is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    try:
        plan = PlanResponse.model_validate(value.plan_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stored_plan_incompatible",
                "message": "Stored plan is incompatible; regenerate it",
            },
        ) from exc
    return PersistedHouseholdPlanView(
        id=value.id,
        household_id=value.household_id,
        user_id=value.user_id,
        schema_version=value.schema_version,
        plan=plan,
        status=HouseholdPlanStatus(value.status),
        version=value.version,
        approved_by_user_id=value.approved_by_user_id,
        approved_at=value.approved_at,
        cancelled_at=value.cancelled_at,
        cancellation_reason=value.cancellation_reason,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _event_view(value: DBHouseholdPlanEvent) -> HouseholdPlanEventView:
    return HouseholdPlanEventView(
        id=value.id,
        plan_id=value.plan_id,
        household_id=value.household_id,
        event_type=HouseholdPlanEventType(value.event_type),
        actor_user_id=value.actor_user_id,
        from_status=HouseholdPlanStatus(value.from_status),
        to_status=HouseholdPlanStatus(value.to_status),
        reason=value.reason,
        metadata=dict(value.event_metadata or {}),
        idempotency_key=value.idempotency_key,
        request_fingerprint=value.request_fingerprint,
        created_at=value.created_at,
    )


def list_household_plans(
    db: Session,
    *,
    household_id: str,
    statuses: Iterable[HouseholdPlanStatus] | None = None,
) -> List[PersistedHouseholdPlanView]:
    query = db.query(DBMealPlan).filter(DBMealPlan.household_id == household_id)
    if statuses:
        values = [status.value for status in statuses]
        query = query.filter(DBMealPlan.status.in_(values))
    rows = query.order_by(DBMealPlan.created_at.desc(), DBMealPlan.id.desc()).all()
    return [_plan_view(value) for value in rows]


def get_household_plan(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
) -> PersistedHouseholdPlanView:
    value = (
        db.query(DBMealPlan)
        .filter(
            DBMealPlan.id == plan_id,
            DBMealPlan.household_id == household_id,
        )
        .first()
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return _plan_view(value)


def list_household_plan_events(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
) -> List[HouseholdPlanEventView]:
    plan = (
        db.query(DBMealPlan.id)
        .filter(
            DBMealPlan.id == plan_id,
            DBMealPlan.household_id == household_id,
        )
        .first()
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    rows = (
        db.query(DBHouseholdPlanEvent)
        .filter(
            DBHouseholdPlanEvent.plan_id == plan_id,
            DBHouseholdPlanEvent.household_id == household_id,
        )
        .order_by(
            DBHouseholdPlanEvent.created_at,
            DBHouseholdPlanEvent.id,
        )
        .all()
    )
    return [_event_view(value) for value in rows]


def assert_approved_source_plan(
    db: Session,
    *,
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
    if plan.status != HouseholdPlanStatus.APPROVED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_plan_not_approved",
                "message": (
                    "Preparation occurrences must reference an approved household plan"
                ),
                "current_status": plan.status,
                "current_version": plan.version,
            },
        )


def _transition_fingerprint(
    *,
    plan_id: int,
    event_type: HouseholdPlanEventType,
    actor_user_id: str,
    payload: HouseholdPlanTransitionRequest,
) -> str:
    return _canonical_hash(
        {
            "plan_id": plan_id,
            "event_type": event_type.value,
            "actor_user_id": actor_user_id,
            "expected_version": payload.expected_version,
            "reason": payload.reason,
            "metadata": payload.metadata,
        }
    )


def _release_active_reservations(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    now: datetime,
) -> int:
    rows = (
        db.query(DBStockReservation)
        .filter(
            DBStockReservation.household_id == household_id,
            DBStockReservation.plan_id == plan_id,
            DBStockReservation.status == ReservationStatus.ACTIVE.value,
        )
        .order_by(DBStockReservation.id)
        .with_for_update()
        .all()
    )
    for value in rows:
        value.status = ReservationStatus.RELEASED.value
        value.version += 1
        value.updated_at = now
        db.add(value)
    return len(rows)


def transition_household_plan(
    db: Session,
    *,
    household_id: str,
    plan_id: int,
    actor_user_id: str,
    event_type: HouseholdPlanEventType,
    payload: HouseholdPlanTransitionRequest,
) -> PersistedHouseholdPlanView:
    _lock_household(db, household_id)
    fingerprint = _transition_fingerprint(
        plan_id=plan_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        payload=payload,
    )
    existing_event = (
        db.query(DBHouseholdPlanEvent)
        .filter(
            DBHouseholdPlanEvent.plan_id == plan_id,
            DBHouseholdPlanEvent.idempotency_key == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing_event is not None:
        if existing_event.request_fingerprint != fingerprint:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "plan_transition_idempotency_conflict",
                    "message": (
                        "Plan transition idempotency key was reused with different content"
                    ),
                },
            )
        return get_household_plan(
            db,
            household_id=household_id,
            plan_id=plan_id,
        )

    plan = (
        db.query(DBMealPlan)
        .filter(
            DBMealPlan.id == plan_id,
            DBMealPlan.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if plan.version != payload.expected_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_plan_version",
                "message": "Household plan was modified",
                "current_version": plan.version,
                "current_status": plan.status,
            },
        )

    previous = HouseholdPlanStatus(plan.status)
    now = utcnow()
    metadata = dict(payload.metadata)
    if event_type == HouseholdPlanEventType.APPROVED:
        if previous != HouseholdPlanStatus.DRAFT:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "invalid_plan_transition",
                    "message": "Only a draft household plan can be approved",
                    "current_status": previous.value,
                },
            )
        next_status = HouseholdPlanStatus.APPROVED
        plan.status = next_status.value
        plan.approved_by_user_id = actor_user_id
        plan.approved_at = now
        plan.cancelled_at = None
        plan.cancellation_reason = None
    elif event_type == HouseholdPlanEventType.CANCELLED:
        if previous not in {
            HouseholdPlanStatus.DRAFT,
            HouseholdPlanStatus.APPROVED,
        }:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "invalid_plan_transition",
                    "message": "Only a draft or approved household plan can be cancelled",
                    "current_status": previous.value,
                },
            )
        next_status = HouseholdPlanStatus.CANCELLED
        plan.status = next_status.value
        plan.cancelled_at = now
        plan.cancellation_reason = payload.reason
        released = _release_active_reservations(
            db,
            household_id=household_id,
            plan_id=plan_id,
            now=now,
        )
        metadata["released_reservation_count"] = released
    else:  # pragma: no cover - enum exhaustiveness guard
        raise HTTPException(status_code=422, detail="Unsupported plan transition")

    plan.version += 1
    plan.updated_at = now
    db.add(plan)
    db.flush()
    db.add(
        DBHouseholdPlanEvent(
            plan_id=plan.id,
            household_id=household_id,
            event_type=event_type.value,
            actor_user_id=actor_user_id,
            from_status=previous.value,
            to_status=next_status.value,
            reason=payload.reason,
            event_metadata=metadata,
            idempotency_key=payload.idempotency_key,
            request_fingerprint=fingerprint,
            created_at=now,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        retry_event = (
            db.query(DBHouseholdPlanEvent)
            .filter(
                DBHouseholdPlanEvent.plan_id == plan_id,
                DBHouseholdPlanEvent.idempotency_key == payload.idempotency_key,
            )
            .first()
        )
        if retry_event is not None:
            if retry_event.request_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "plan_transition_idempotency_conflict",
                        "message": (
                            "Plan transition idempotency key was reused with different content"
                        ),
                    },
                ) from exc
            return get_household_plan(
                db,
                household_id=household_id,
                plan_id=plan_id,
            )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "plan_transition_conflict",
                "message": "Plan transition conflicted with concurrent state",
            },
        ) from exc
    db.refresh(plan)
    return _plan_view(plan)
