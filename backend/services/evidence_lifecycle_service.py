"""Append-only lifecycle operations for immutable food-evidence versions."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.evidence_lifecycle import (
    EvidenceLifecycleBatchDocument,
    EvidenceLifecycleBatchResult,
    EvidenceLifecycleEventView,
    EvidenceLifecycleRequest,
    EvidenceTargetKind,
)
from backend.evidence_history_models import (
    DBEvidenceLifecycleEvent,
    DBIngredientConversionVersion,
    DBStoragePolicyVersion,
)
from backend.services.evidence_history_service import _lock_evidence_key, utcnow


def lifecycle_request_fingerprint(payload: EvidenceLifecycleRequest) -> str:
    raw = json.dumps(
        {
            "target_kind": payload.target_kind.value,
            "target_id": payload.target_id,
            "action": payload.action.value,
            "actor": payload.actor,
            "reason": payload.reason,
            "metadata": payload.metadata,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _target(
    db: Session,
    payload: EvidenceLifecycleRequest,
    *,
    for_update: bool,
):
    if payload.target_kind == EvidenceTargetKind.CONVERSION:
        query = db.query(DBIngredientConversionVersion).filter(
            DBIngredientConversionVersion.id == payload.target_id
        )
    else:
        query = db.query(DBStoragePolicyVersion).filter(
            DBStoragePolicyVersion.id == payload.target_id
        )
    if for_update:
        query = query.with_for_update()
    value = query.first()
    if value is None:
        raise ValueError(
            f"Unknown {payload.target_kind.value} evidence target ID {payload.target_id}"
        )
    return value


def _natural_lock_key(payload: EvidenceLifecycleRequest, target) -> tuple[str, str]:
    if payload.target_kind == EvidenceTargetKind.CONVERSION:
        return (
            "conversion",
            f"{target.canonical_name}|{target.from_unit}|{target.to_unit}",
        )
    return "storage-policy", str(target.policy_key)


def _event_target_id(value: DBEvidenceLifecycleEvent) -> int:
    target_id = (
        value.conversion_version_id
        if value.evidence_kind == EvidenceTargetKind.CONVERSION.value
        else value.storage_policy_version_id
    )
    if target_id is None:
        raise RuntimeError("Evidence lifecycle event has no target")
    return int(target_id)


def _event_view(
    db: Session,
    value: DBEvidenceLifecycleEvent,
) -> EvidenceLifecycleEventView:
    target_id = _event_target_id(value)
    if value.evidence_kind == EvidenceTargetKind.CONVERSION.value:
        target = db.get(DBIngredientConversionVersion, target_id)
        if target is None:
            raise RuntimeError("Lifecycle conversion target is missing")
        record_version = target.record_version
    else:
        target = db.get(DBStoragePolicyVersion, target_id)
        if target is None:
            raise RuntimeError("Lifecycle storage-policy target is missing")
        record_version = target.policy_version
    return EvidenceLifecycleEventView(
        id=value.id,
        target_kind=EvidenceTargetKind(value.evidence_kind),
        target_id=target_id,
        action=value.action,
        actor=value.actor,
        reason=value.reason,
        metadata=dict(value.event_metadata or {}),
        idempotency_key=value.idempotency_key,
        request_fingerprint=value.request_fingerprint,
        target_record_version=record_version,
        target_content_hash=target.content_hash,
        target_was_active=bool(value.target_was_active),
        created_at=value.created_at.isoformat(),
    )


def _validate_existing_event(
    value: DBEvidenceLifecycleEvent,
    payload: EvidenceLifecycleRequest,
    fingerprint: str,
) -> None:
    expected_target_id = _event_target_id(value)
    if (
        value.request_fingerprint != fingerprint
        or value.evidence_kind != payload.target_kind.value
        or expected_target_id != payload.target_id
        or value.action != payload.action.value
    ):
        raise ValueError(
            "Evidence lifecycle idempotency key already exists with a different request"
        )


def apply_evidence_lifecycle_batch(
    db: Session,
    document: EvidenceLifecycleBatchDocument,
) -> EvidenceLifecycleBatchResult:
    actions = sorted(
        document.actions,
        key=lambda value: (
            value.target_kind.value,
            value.target_id,
            value.idempotency_key,
        ),
    )

    # Resolve natural keys without mutation, then acquire all transaction locks
    # in one deterministic order to prevent cross-batch deadlocks.
    lock_requests: set[tuple[str, str]] = {
        ("evidence-lifecycle", value.idempotency_key) for value in actions
    }
    for payload in actions:
        target = _target(db, payload, for_update=False)
        lock_requests.add(_natural_lock_key(payload, target))
    for namespace, key in sorted(lock_requests):
        _lock_evidence_key(db, namespace, key)

    events: list[DBEvidenceLifecycleEvent] = []
    idempotent_count = 0
    changed_count = 0
    already_inactive_count = 0
    now = utcnow()

    try:
        for payload in actions:
            fingerprint = lifecycle_request_fingerprint(payload)
            existing = (
                db.query(DBEvidenceLifecycleEvent)
                .filter(
                    DBEvidenceLifecycleEvent.idempotency_key
                    == payload.idempotency_key
                )
                .with_for_update()
                .first()
            )
            if existing is not None:
                _validate_existing_event(existing, payload, fingerprint)
                events.append(existing)
                idempotent_count += 1
                continue

            target = _target(db, payload, for_update=True)
            target_was_active = bool(target.active)
            if target_was_active:
                target.active = False
                target.updated_at = now
                db.add(target)
                db.flush()
                changed_count += 1
            else:
                already_inactive_count += 1

            event = DBEvidenceLifecycleEvent(
                evidence_kind=payload.target_kind.value,
                conversion_version_id=(
                    payload.target_id
                    if payload.target_kind == EvidenceTargetKind.CONVERSION
                    else None
                ),
                storage_policy_version_id=(
                    payload.target_id
                    if payload.target_kind == EvidenceTargetKind.STORAGE_POLICY
                    else None
                ),
                action=payload.action.value,
                actor=payload.actor,
                reason=payload.reason,
                event_metadata=dict(payload.metadata),
                idempotency_key=payload.idempotency_key,
                request_fingerprint=fingerprint,
                target_was_active=target_was_active,
                created_at=now,
            )
            db.add(event)
            db.flush()
            events.append(event)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(
            "Evidence lifecycle batch conflicted with concurrent state; no new lifecycle events were committed"
        ) from exc
    except Exception:
        db.rollback()
        raise

    return EvidenceLifecycleBatchResult(
        events=[_event_view(db, value) for value in events],
        changed_target_count=changed_count,
        already_inactive_count=already_inactive_count,
        idempotent_count=idempotent_count,
    )


def list_evidence_lifecycle_events(
    db: Session,
    *,
    target_kind: EvidenceTargetKind | None = None,
    target_id: int | None = None,
    limit: int = 500,
) -> List[EvidenceLifecycleEventView]:
    query = db.query(DBEvidenceLifecycleEvent)
    if target_kind is not None:
        query = query.filter(
            DBEvidenceLifecycleEvent.evidence_kind == target_kind.value
        )
    if target_id is not None:
        if target_kind is None:
            raise ValueError("target_kind is required when target_id is supplied")
        if target_kind == EvidenceTargetKind.CONVERSION:
            query = query.filter(
                DBEvidenceLifecycleEvent.conversion_version_id == target_id
            )
        else:
            query = query.filter(
                DBEvidenceLifecycleEvent.storage_policy_version_id == target_id
            )
    rows = query.order_by(
        DBEvidenceLifecycleEvent.created_at.desc(),
        DBEvidenceLifecycleEvent.id.desc(),
    ).limit(max(1, min(limit, 5000))).all()
    return [_event_view(db, value) for value in rows]
