"""Non-mutating preflight for immutable evidence lifecycle documents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Literal

from sqlalchemy.orm import Session

from backend.domain.evidence_lifecycle import EvidenceLifecycleBatchDocument
from backend.evidence_history_models import DBEvidenceLifecycleEvent
from backend.services.evidence_lifecycle_service import (
    _event_target_id,
    _target,
    _validate_existing_event,
    lifecycle_request_fingerprint,
)


LifecyclePlannedAction = Literal[
    "idempotent_existing",
    "deactivate_active_target",
    "record_action_on_inactive_target",
]


@dataclass(frozen=True)
class EvidenceLifecyclePreview:
    target_kind: str
    target_id: int
    target_record_version: str
    target_content_hash: str
    target_active: bool
    action: str
    actor: str
    reason: str
    idempotency_key: str
    request_fingerprint: str
    planned_action: LifecyclePlannedAction
    existing_event_id: int | None

    def to_dict(self) -> dict:
        return asdict(self)


def preflight_evidence_lifecycle_batch(
    db: Session,
    document: EvidenceLifecycleBatchDocument,
) -> List[EvidenceLifecyclePreview]:
    previews: List[EvidenceLifecyclePreview] = []
    for payload in sorted(
        document.actions,
        key=lambda value: (
            value.target_kind.value,
            value.target_id,
            value.idempotency_key,
        ),
    ):
        target = _target(db, payload, for_update=False)
        fingerprint = lifecycle_request_fingerprint(payload)
        existing = (
            db.query(DBEvidenceLifecycleEvent)
            .filter(
                DBEvidenceLifecycleEvent.idempotency_key
                == payload.idempotency_key
            )
            .first()
        )
        if existing is not None:
            _validate_existing_event(existing, payload, fingerprint)
            if _event_target_id(existing) != payload.target_id:
                raise ValueError("Lifecycle event target mismatch")
            planned_action: LifecyclePlannedAction = "idempotent_existing"
            existing_event_id = existing.id
        elif target.active:
            planned_action = "deactivate_active_target"
            existing_event_id = None
        else:
            planned_action = "record_action_on_inactive_target"
            existing_event_id = None
        record_version = (
            target.record_version
            if payload.target_kind.value == "conversion"
            else target.policy_version
        )
        previews.append(
            EvidenceLifecyclePreview(
                target_kind=payload.target_kind.value,
                target_id=payload.target_id,
                target_record_version=record_version,
                target_content_hash=target.content_hash,
                target_active=bool(target.active),
                action=payload.action.value,
                actor=payload.actor,
                reason=payload.reason,
                idempotency_key=payload.idempotency_key,
                request_fingerprint=fingerprint,
                planned_action=planned_action,
                existing_event_id=existing_event_id,
            )
        )
    return previews
