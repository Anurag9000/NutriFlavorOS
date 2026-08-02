"""Compute structural household coverage for schedule derivation evidence."""

from __future__ import annotations

from collections import Counter
from typing import Dict

from sqlalchemy.orm import Session

from backend.database import utcnow
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalStatus,
)
from backend.domain.preparation_schedule_derivation import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
)
from backend.domain.preparation_schedule_derivation_coverage import (
    PreparationScheduleDerivationCoverageView,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _repair_evidence_complete(
    schedule: DBPersistedPreparationSchedule,
    proposal: DBPreparationRepairProposal | None,
    acceptance: DBPreparationRepairProposalAcceptance | None,
) -> bool:
    if proposal is None or acceptance is None:
        return False
    if proposal.status != PreparationRepairProposalStatus.ACCEPTED.value:
        return False
    comparisons = [
        proposal.id == schedule.source_repair_proposal_id,
        proposal.version == schedule.source_repair_proposal_version,
        acceptance.proposal_id == proposal.id,
        acceptance.proposal_version_after == proposal.version,
        acceptance.created_schedule_id == schedule.id,
        acceptance.created_schedule_version == 1,
        acceptance.derivation_method == REPAIR_SCHEDULER_METHOD,
        proposal.source_schedule_id == acceptance.source_schedule_id,
        proposal.source_schedule_version == acceptance.source_schedule_version,
        proposal.source_schedule_hash == acceptance.source_schedule_hash,
        proposal.source_schedule_request_hash
        == acceptance.source_schedule_request_hash,
        proposal.target_calendar_content_hash
        == acceptance.target_calendar_content_hash,
        proposal.repair_request_hash == acceptance.repair_request_hash,
        proposal.repair_request_hash == schedule.source_repair_request_hash,
        proposal.repair_result_hash == acceptance.repair_result_hash,
        proposal.repair_result_hash == schedule.source_repair_result_hash,
        proposal.revised_request_hash == acceptance.revised_request_hash,
        proposal.revised_request_hash == schedule.source_revised_request_hash,
        proposal.repaired_response_hash == acceptance.repaired_response_hash,
        proposal.repaired_response_hash == schedule.source_repaired_response_hash,
        sorted(proposal.required_acknowledgement_task_ids or [])
        == sorted(acceptance.acknowledged_task_ids or []),
    ]
    return all(comparisons)


def get_schedule_derivation_coverage(
    db: Session,
    *,
    household_id: str,
) -> PreparationScheduleDerivationCoverageView:
    schedules = (
        db.query(DBPersistedPreparationSchedule)
        .filter(DBPersistedPreparationSchedule.household_id == household_id)
        .order_by(DBPersistedPreparationSchedule.id.asc())
        .all()
    )
    proposals = (
        db.query(DBPreparationRepairProposal)
        .filter(DBPreparationRepairProposal.household_id == household_id)
        .all()
    )
    acceptances = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.household_id == household_id)
        .all()
    )
    proposal_by_id: Dict[int, DBPreparationRepairProposal] = {
        value.id: value for value in proposals
    }
    acceptance_by_schedule: Dict[int, DBPreparationRepairProposalAcceptance] = {
        value.created_schedule_id: value for value in acceptances
    }

    execution_schedule_ids = {
        int(value[0])
        for value in (
            db.query(DBPreparationTaskExecutionEvent.schedule_id)
            .filter(DBPreparationTaskExecutionEvent.household_id == household_id)
            .distinct()
            .all()
        )
    }

    method_counts: Counter[str] = Counter()
    original_count = 0
    repair_count = 0
    unknown_count = 0
    complete_count = 0
    repaired_draft_count = 0
    repaired_approved_count = 0
    repaired_execution_count = 0
    warnings: list[str] = []

    for schedule in schedules:
        method = schedule.derivation_method or ORIGINAL_SCHEDULER_METHOD
        method_counts[method] += 1
        if method == ORIGINAL_SCHEDULER_METHOD:
            original_count += 1
            repair_columns = [
                schedule.source_repair_proposal_id,
                schedule.source_repair_proposal_version,
                schedule.source_repair_request_hash,
                schedule.source_repair_result_hash,
                schedule.source_revised_request_hash,
                schedule.source_repaired_response_hash,
            ]
            if all(value is None for value in repair_columns):
                complete_count += 1
            else:
                warnings.append(
                    f"schedule {schedule.id} reports original derivation with repair fields"
                )
            continue

        if method == REPAIR_SCHEDULER_METHOD:
            repair_count += 1
            if schedule.status == "draft":
                repaired_draft_count += 1
            elif schedule.status == "approved":
                repaired_approved_count += 1
            if schedule.id in execution_schedule_ids:
                repaired_execution_count += 1
            proposal = (
                proposal_by_id.get(schedule.source_repair_proposal_id)
                if schedule.source_repair_proposal_id is not None
                else None
            )
            acceptance = acceptance_by_schedule.get(schedule.id)
            if _repair_evidence_complete(schedule, proposal, acceptance):
                complete_count += 1
            else:
                warnings.append(
                    f"schedule {schedule.id} has incomplete repair derivation evidence"
                )
            continue

        unknown_count += 1
        warnings.append(
            f"schedule {schedule.id} uses unknown derivation method {method}"
        )

    total = len(schedules)
    incomplete = total - complete_count
    accepted_proposal_count = sum(
        value.status == PreparationRepairProposalStatus.ACCEPTED.value
        for value in proposals
    )
    latest_acceptance = max(
        (value.created_at for value in acceptances),
        default=None,
    )

    return PreparationScheduleDerivationCoverageView(
        household_id=household_id,
        generated_at=utcnow().isoformat(),
        schedule_total=total,
        original_schedule_count=original_count,
        repair_schedule_count=repair_count,
        unknown_method_count=unknown_count,
        complete_derivation_count=complete_count,
        incomplete_derivation_count=incomplete,
        accepted_proposal_count=accepted_proposal_count,
        acceptance_record_count=len(acceptances),
        repaired_draft_count=repaired_draft_count,
        repaired_approved_count=repaired_approved_count,
        repaired_execution_history_count=repaired_execution_count,
        method_counts=dict(sorted(method_counts.items())),
        derivation_coverage_ratio=_ratio(complete_count, total),
        repair_acceptance_link_coverage_ratio=_ratio(
            repair_count - sum(
                1
                for schedule in schedules
                if (schedule.derivation_method or ORIGINAL_SCHEDULER_METHOD)
                == REPAIR_SCHEDULER_METHOD
                and not _repair_evidence_complete(
                    schedule,
                    proposal_by_id.get(schedule.source_repair_proposal_id)
                    if schedule.source_repair_proposal_id is not None
                    else None,
                    acceptance_by_schedule.get(schedule.id),
                )
            ),
            repair_count,
        ),
        latest_acceptance_at=(
            latest_acceptance.isoformat() if latest_acceptance else None
        ),
        warnings=sorted(set(warnings)),
    )


__all__ = ["get_schedule_derivation_coverage"]
