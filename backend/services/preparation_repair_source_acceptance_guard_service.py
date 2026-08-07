"""Authoritative source-level guard for repaired-draft acceptance.

Multiple advisory proposals may exist for one source schedule version. Exactly
one may cross the explicit acceptance boundary and create a replacement draft.
The database uniqueness constraint remains the final concurrency authority.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
    PreparationRepairProposalAcceptedDraftView,
    PreparationRepairProposalEventType,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_execution_snapshot_service import (
    assert_preparation_execution_snapshot_unchanged,
)
from backend.services.preparation_operations_service import _lock_household
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
)


def _proposal_execution_snapshot_hash(
    db: Session,
    *,
    proposal: DBPreparationRepairProposal,
) -> str:
    """Load immutable creation-time execution identity for an unaccepted proposal."""

    created_event = (
        db.query(DBPreparationRepairProposalEvent)
        .filter(
            DBPreparationRepairProposalEvent.proposal_id == proposal.id,
            DBPreparationRepairProposalEvent.event_type
            == PreparationRepairProposalEventType.CREATED.value,
        )
        .order_by(DBPreparationRepairProposalEvent.id.asc())
        .with_for_update()
        .first()
    )
    metadata = dict(created_event.event_metadata or {}) if created_event else {}
    snapshot_hash = metadata.get("execution_snapshot_hash")
    if not isinstance(snapshot_hash, str) or len(snapshot_hash) != 64:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_execution_snapshot_evidence_missing",
                "message": (
                    "Repair proposal lacks canonical creation-time execution "
                    "snapshot evidence and cannot be accepted safely"
                ),
                "proposal_id": proposal.id,
            },
        )

    if (
        metadata.get("source_schedule_id") != proposal.source_schedule_id
        or metadata.get("source_schedule_version") != proposal.source_schedule_version
        or metadata.get("execution_event_count") != 0
        or metadata.get("latest_execution_event_id") is not None
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_acceptance_execution_snapshot_evidence_invalid",
                "message": (
                    "Ordinary repair proposal execution evidence does not match "
                    "its immutable source identity"
                ),
                "proposal_id": proposal.id,
            },
        )
    return snapshot_hash


def accept_repair_proposal_with_source_guard(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
    actor_user_id: str,
    payload: PreparationRepairProposalAcceptRequest,
) -> PreparationRepairProposalAcceptedDraftView:
    """Accept only when source replacement and execution identities remain current."""

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

    existing = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.household_id == household_id,
            DBPreparationRepairProposalAcceptance.source_schedule_id
            == proposal.source_schedule_id,
            DBPreparationRepairProposalAcceptance.source_schedule_version
            == proposal.source_schedule_version,
        )
        .with_for_update()
        .first()
    )
    if existing is not None and existing.proposal_id != proposal.id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_source_already_has_accepted_replacement",
                "message": (
                    "This source schedule version already has an accepted repair "
                    "replacement"
                ),
                "source_schedule_id": proposal.source_schedule_id,
                "source_schedule_version": proposal.source_schedule_version,
                "accepted_proposal_id": existing.proposal_id,
                "accepted_schedule_id": existing.created_schedule_id,
                "acceptance_id": existing.id,
            },
        )

    # Preserve exact idempotent recovery after a successful acceptance. Before an
    # unaccepted proposal may cross the mutation boundary, however, the canonical
    # execution ledger must still match the immutable snapshot captured when the
    # proposal was created. Task-execution mutations share this household lock,
    # so no event can race between this comparison and acceptance.
    if existing is None:
        expected_snapshot_hash = _proposal_execution_snapshot_hash(
            db,
            proposal=proposal,
        )
        assert_preparation_execution_snapshot_unchanged(
            db,
            household_id=household_id,
            schedule_id=proposal.source_schedule_id,
            expected_execution_snapshot_hash=expected_snapshot_hash,
        )

    return accept_repair_proposal(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


__all__ = ["accept_repair_proposal_with_source_guard"]
