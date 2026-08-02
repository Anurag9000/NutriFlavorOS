"""Locked cross-record guard for approval of repair-derived drafts.

The method-aware replay service validates algorithmic evidence. This guard
additionally validates the immutable acceptance row against the proposal,
source schedule identity, and created draft before delegating to approval.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation_operations import (
    PersistedPreparationScheduleView,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalStatus,
)
from backend.domain.preparation_schedule_replay import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_operations_service import _lock_household
from backend.services.preparation_schedule_approval_service import (
    approve_schedule_authoritative,
)


def _mismatch(
    *,
    field: str,
    expected: object,
    observed: object,
) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "repair_approval_acceptance_mismatch",
            "message": f"Repair acceptance evidence disagrees for {field}",
            "field": field,
            "expected": expected,
            "observed": observed,
        },
    )


def _assert_equal(field: str, expected: object, observed: object) -> None:
    if expected != observed:
        raise _mismatch(field=field, expected=expected, observed=observed)


def approve_schedule_with_repair_acceptance_guard(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    payload: ScheduleStateTransitionRequest,
) -> PersistedPreparationScheduleView:
    """Approve after locking and validating cross-record acceptance evidence."""

    _lock_household(db, household_id)
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

    method = schedule.derivation_method or ORIGINAL_SCHEDULER_METHOD
    if method == ORIGINAL_SCHEDULER_METHOD:
        return approve_schedule_authoritative(
            db,
            household_id=household_id,
            schedule_id=schedule_id,
            actor_user_id=actor_user_id,
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
    if schedule.source_repair_proposal_id is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_approval_proposal_link_missing",
                "message": "Repair-derived draft lacks a source proposal link",
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
    acceptance = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.proposal_id
            == schedule.source_repair_proposal_id,
            DBPreparationRepairProposalAcceptance.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if proposal is None or acceptance is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_approval_acceptance_evidence_missing",
                "message": "Repair-derived draft lacks proposal or acceptance evidence",
            },
        )
    if proposal.status != PreparationRepairProposalStatus.ACCEPTED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_approval_proposal_not_accepted",
                "message": "Source repair proposal is not accepted",
                "status": proposal.status,
            },
        )

    comparisons = [
        ("acceptance_proposal_id", proposal.id, acceptance.proposal_id),
        ("created_schedule_id", schedule.id, acceptance.created_schedule_id),
        ("created_schedule_version", 1, acceptance.created_schedule_version),
        ("acceptance_method", REPAIR_SCHEDULER_METHOD, acceptance.derivation_method),
        ("schedule_method", REPAIR_SCHEDULER_METHOD, schedule.derivation_method),
        (
            "proposal_version_after",
            proposal.version,
            acceptance.proposal_version_after,
        ),
        (
            "schedule_proposal_version",
            proposal.version,
            schedule.source_repair_proposal_version,
        ),
        (
            "proposal_version_increment",
            acceptance.proposal_version_before + 1,
            acceptance.proposal_version_after,
        ),
        (
            "source_schedule_id",
            proposal.source_schedule_id,
            acceptance.source_schedule_id,
        ),
        (
            "source_schedule_version",
            proposal.source_schedule_version,
            acceptance.source_schedule_version,
        ),
        (
            "source_schedule_hash",
            proposal.source_schedule_hash,
            acceptance.source_schedule_hash,
        ),
        (
            "source_schedule_request_hash",
            proposal.source_schedule_request_hash,
            acceptance.source_schedule_request_hash,
        ),
        (
            "target_calendar_content_hash",
            proposal.target_calendar_content_hash,
            acceptance.target_calendar_content_hash,
        ),
        (
            "acceptance_repair_request_hash",
            proposal.repair_request_hash,
            acceptance.repair_request_hash,
        ),
        (
            "schedule_repair_request_hash",
            proposal.repair_request_hash,
            schedule.source_repair_request_hash,
        ),
        (
            "acceptance_repair_result_hash",
            proposal.repair_result_hash,
            acceptance.repair_result_hash,
        ),
        (
            "schedule_repair_result_hash",
            proposal.repair_result_hash,
            schedule.source_repair_result_hash,
        ),
        (
            "acceptance_revised_request_hash",
            proposal.revised_request_hash,
            acceptance.revised_request_hash,
        ),
        (
            "schedule_revised_request_hash",
            proposal.revised_request_hash,
            schedule.source_revised_request_hash,
        ),
        (
            "acceptance_repaired_response_hash",
            proposal.repaired_response_hash,
            acceptance.repaired_response_hash,
        ),
        (
            "schedule_repaired_response_hash",
            proposal.repaired_response_hash,
            schedule.source_repaired_response_hash,
        ),
        (
            "acknowledged_task_ids",
            sorted(proposal.required_acknowledgement_task_ids or []),
            sorted(acceptance.acknowledged_task_ids or []),
        ),
    ]
    for field, expected, observed in comparisons:
        _assert_equal(field, expected, observed)

    return approve_schedule_authoritative(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


__all__ = ["approve_schedule_with_repair_acceptance_guard"]
