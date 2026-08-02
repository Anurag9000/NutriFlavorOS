"""Authoritative read-only resolution of preparation schedule derivation."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalStatus,
)
from backend.domain.preparation_schedule_derivation import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
    PreparationScheduleDerivationEvidenceView,
)
from backend.domain.preparation_schedule_replay import (
    PreparationScheduleDerivationMethod,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)


def _conflict(
    *,
    code: str,
    message: str,
    field: str | None = None,
    expected: object | None = None,
    observed: object | None = None,
) -> HTTPException:
    detail: dict[str, object] = {"code": code, "message": message}
    if field is not None:
        detail.update(
            {
                "field": field,
                "expected": expected,
                "observed": observed,
            }
        )
    return HTTPException(status_code=409, detail=detail)


def _assert_equal(field: str, expected: object, observed: object) -> None:
    if expected != observed:
        raise _conflict(
            code="schedule_derivation_evidence_mismatch",
            message=f"Schedule derivation evidence disagrees for {field}",
            field=field,
            expected=expected,
            observed=observed,
        )


def get_schedule_derivation_evidence(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> PreparationScheduleDerivationEvidenceView:
    schedule = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    method = schedule.derivation_method or ORIGINAL_SCHEDULER_METHOD
    if method == ORIGINAL_SCHEDULER_METHOD:
        repair_columns = [
            schedule.source_repair_proposal_id,
            schedule.source_repair_proposal_version,
            schedule.source_repair_request_hash,
            schedule.source_repair_result_hash,
            schedule.source_revised_request_hash,
            schedule.source_repaired_response_hash,
        ]
        if any(value is not None for value in repair_columns):
            raise _conflict(
                code="original_schedule_has_repair_evidence",
                message=(
                    "Original scheduler record contains contradictory repair evidence"
                ),
            )
        return PreparationScheduleDerivationEvidenceView(
            schedule_id=schedule.id,
            household_id=schedule.household_id,
            schedule_version=schedule.version,
            schedule_status=schedule.status,
            schedule_hash=schedule.schedule_hash,
            derivation_method=PreparationScheduleDerivationMethod.ORIGINAL,
            evidence_complete=True,
            source_repair_proposal_id=None,
            source_repair_proposal_version=None,
            source_repair_acceptance_id=None,
            source_schedule_id=None,
            source_schedule_version=None,
            source_schedule_hash=None,
            source_schedule_request_hash=None,
            target_calendar_content_hash=None,
            repair_request_hash=None,
            repair_result_hash=None,
            revised_request_hash=None,
            repaired_response_hash=None,
            accepted_by_user_id=None,
            accepted_at=None,
            acceptance_reason=None,
            warnings=[],
            created_at=schedule.created_at.isoformat(),
            updated_at=schedule.updated_at.isoformat(),
        )

    if method != REPAIR_SCHEDULER_METHOD:
        raise _conflict(
            code="unknown_schedule_derivation_method",
            message="Persisted schedule derivation method is not supported",
            field="derivation_method",
            expected=[ORIGINAL_SCHEDULER_METHOD, REPAIR_SCHEDULER_METHOD],
            observed=method,
        )
    if schedule.source_repair_proposal_id is None:
        raise _conflict(
            code="repair_schedule_proposal_link_missing",
            message="Repair-derived schedule lacks a source proposal link",
        )

    proposal = (
        db.query(DBPreparationRepairProposal)
        .filter(
            DBPreparationRepairProposal.id == schedule.source_repair_proposal_id,
            DBPreparationRepairProposal.household_id == household_id,
        )
        .first()
    )
    acceptance = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.proposal_id
            == schedule.source_repair_proposal_id,
            DBPreparationRepairProposalAcceptance.household_id == household_id,
            DBPreparationRepairProposalAcceptance.created_schedule_id == schedule.id,
        )
        .first()
    )
    if proposal is None or acceptance is None:
        raise _conflict(
            code="repair_schedule_derivation_evidence_missing",
            message=(
                "Repair-derived schedule lacks its proposal or acceptance evidence"
            ),
        )
    if proposal.status != PreparationRepairProposalStatus.ACCEPTED.value:
        raise _conflict(
            code="repair_schedule_proposal_not_accepted",
            message="Repair-derived schedule source proposal is not accepted",
            field="proposal_status",
            expected=PreparationRepairProposalStatus.ACCEPTED.value,
            observed=proposal.status,
        )

    comparisons = [
        (
            "schedule_proposal_version",
            proposal.version,
            schedule.source_repair_proposal_version,
        ),
        (
            "acceptance_proposal_version",
            proposal.version,
            acceptance.proposal_version_after,
        ),
        (
            "created_schedule_version",
            1,
            acceptance.created_schedule_version,
        ),
        (
            "acceptance_method",
            REPAIR_SCHEDULER_METHOD,
            acceptance.derivation_method,
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
            "schedule_repair_request_hash",
            proposal.repair_request_hash,
            schedule.source_repair_request_hash,
        ),
        (
            "acceptance_repair_request_hash",
            proposal.repair_request_hash,
            acceptance.repair_request_hash,
        ),
        (
            "schedule_repair_result_hash",
            proposal.repair_result_hash,
            schedule.source_repair_result_hash,
        ),
        (
            "acceptance_repair_result_hash",
            proposal.repair_result_hash,
            acceptance.repair_result_hash,
        ),
        (
            "schedule_revised_request_hash",
            proposal.revised_request_hash,
            schedule.source_revised_request_hash,
        ),
        (
            "acceptance_revised_request_hash",
            proposal.revised_request_hash,
            acceptance.revised_request_hash,
        ),
        (
            "schedule_repaired_response_hash",
            proposal.repaired_response_hash,
            schedule.source_repaired_response_hash,
        ),
        (
            "acceptance_repaired_response_hash",
            proposal.repaired_response_hash,
            acceptance.repaired_response_hash,
        ),
        (
            "acknowledged_task_ids",
            sorted(proposal.required_acknowledgement_task_ids or []),
            sorted(acceptance.acknowledged_task_ids or []),
        ),
    ]
    for field, expected, observed in comparisons:
        _assert_equal(field, expected, observed)

    return PreparationScheduleDerivationEvidenceView(
        schedule_id=schedule.id,
        household_id=schedule.household_id,
        schedule_version=schedule.version,
        schedule_status=schedule.status,
        schedule_hash=schedule.schedule_hash,
        derivation_method=PreparationScheduleDerivationMethod.REPAIR,
        evidence_complete=True,
        source_repair_proposal_id=proposal.id,
        source_repair_proposal_version=proposal.version,
        source_repair_acceptance_id=acceptance.id,
        source_schedule_id=acceptance.source_schedule_id,
        source_schedule_version=acceptance.source_schedule_version,
        source_schedule_hash=acceptance.source_schedule_hash,
        source_schedule_request_hash=acceptance.source_schedule_request_hash,
        target_calendar_content_hash=acceptance.target_calendar_content_hash,
        repair_request_hash=acceptance.repair_request_hash,
        repair_result_hash=acceptance.repair_result_hash,
        revised_request_hash=acceptance.revised_request_hash,
        repaired_response_hash=acceptance.repaired_response_hash,
        accepted_by_user_id=acceptance.actor_user_id,
        accepted_at=acceptance.created_at.isoformat(),
        acceptance_reason=acceptance.reason,
        warnings=[],
        created_at=schedule.created_at.isoformat(),
        updated_at=schedule.updated_at.isoformat(),
    )


__all__ = ["get_schedule_derivation_evidence"]
