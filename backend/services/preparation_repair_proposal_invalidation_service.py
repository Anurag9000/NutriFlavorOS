"""Owner-authorized invalidation for immutable preparation repair proposals."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import utcnow
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalEventType,
    PreparationRepairProposalInvalidateRequest,
    PreparationRepairProposalStatus,
    PreparationRepairProposalView,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_operations_service import _lock_household
from backend.services.preparation_repair_proposal_read_service import (
    _proposal_view,
    _stale_reasons,
)
from backend.services.preparation_repair_proposal_service import (
    _canonical_hash,
    _event,
)


def _fingerprint(
    payload: PreparationRepairProposalInvalidateRequest,
    *,
    household_id: str,
    proposal_id: int,
    actor_user_id: str,
) -> str:
    return _canonical_hash(
        {
            "action": "invalidate_repair_proposal",
            "household_id": household_id,
            "proposal_id": proposal_id,
            "actor_user_id": actor_user_id,
            "payload": payload.model_dump(mode="json"),
        }
    )


def invalidate_repair_proposal(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
    actor_user_id: str,
    payload: PreparationRepairProposalInvalidateRequest,
) -> PreparationRepairProposalView:
    """Withdraw one proposed record without accepting or persisting a schedule."""

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

    fingerprint = _fingerprint(
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
        if (
            existing_event.event_type
            != PreparationRepairProposalEventType.INVALIDATED.value
            or existing_event.request_fingerprint != fingerprint
        ):
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
                "code": "repair_proposal_not_invalidatable",
                "message": "Only proposed repair records can be invalidated",
                "status": proposal.status,
            },
        )

    observed_stale_reasons = _stale_reasons(db, proposal)
    before = proposal.version
    now = utcnow()
    proposal.status = PreparationRepairProposalStatus.INVALIDATED.value
    proposal.version += 1
    proposal.updated_at = now
    db.add(proposal)

    event_metadata = dict(payload.metadata)
    event_metadata.update(
        {
            "observed_stale_reasons": observed_stale_reasons,
            "historical_only": True,
            "accepted": False,
            "schedule_persistence_performed": False,
            "approval_performed": False,
            "execution_performed": False,
        }
    )
    _event(
        db,
        proposal=proposal,
        event_type=PreparationRepairProposalEventType.INVALIDATED,
        actor_user_id=actor_user_id,
        from_status=PreparationRepairProposalStatus.PROPOSED.value,
        to_status=PreparationRepairProposalStatus.INVALIDATED.value,
        reason=payload.reason,
        metadata=event_metadata,
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
                "code": "repair_proposal_invalidation_conflict",
                "message": (
                    "Repair proposal invalidation conflicted with concurrent state"
                ),
            },
        ) from exc
    db.refresh(proposal)
    return _proposal_view(db, proposal)


__all__ = ["invalidate_repair_proposal"]
