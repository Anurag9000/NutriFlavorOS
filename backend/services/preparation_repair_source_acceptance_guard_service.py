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
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_operations_service import _lock_household
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
)


def accept_repair_proposal_with_source_guard(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
    actor_user_id: str,
    payload: PreparationRepairProposalAcceptRequest,
) -> PreparationRepairProposalAcceptedDraftView:
    """Accept only when the source schedule version has no other acceptance."""

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

    return accept_repair_proposal(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


__all__ = ["accept_repair_proposal_with_source_guard"]
