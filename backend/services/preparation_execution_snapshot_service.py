"""Build, revalidate, and project execution snapshots for repair authority."""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.database import utcnow
from backend.domain.preparation import PreparationScheduleResponse
from backend.domain.preparation_execution_snapshot import (
    EXECUTION_SNAPSHOT_VERSION,
    PreparationExecutionSnapshot,
    PreparationExecutionTaskSnapshot,
    execution_event_ledger_hash,
    preparation_execution_snapshot_hash,
)
from backend.domain.preparation_repair_task_lineage import (
    PreparationRepairTaskLineage,
    derive_preparation_repair_task_lineage,
)
from backend.domain.preparation_task_execution import PreparationTaskExecutionState
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_task_execution_service import (
    get_task_execution_overview,
)


def get_preparation_execution_snapshot(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> PreparationExecutionSnapshot:
    """Read one execution ledger/state projection and return its stable identity.

    Mutation paths that use this for repair authority must hold the household
    serialization lock before calling it. All task-execution mutations already
    acquire that lock, so proposal creation/acceptance can compare an exact
    ledger snapshot without copying or mutating historical execution events.
    """

    overview = get_task_execution_overview(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    task_states = sorted(
        (
            PreparationExecutionTaskSnapshot(
                task_id=value.task.task_id,
                state=value.state,
                latest_event_id=value.latest_event_id,
            )
            for value in overview.tasks
        ),
        key=lambda value: value.task_id,
    )
    frozen = sorted(
        value.task_id
        for value in task_states
        if value.state
        in {
            PreparationTaskExecutionState.COMPLETED,
            PreparationTaskExecutionState.SKIPPED,
        }
    )
    repairable = sorted(
        value.task_id
        for value in task_states
        if value.state == PreparationTaskExecutionState.PLANNED
    )
    in_progress = sorted(
        value.task_id
        for value in task_states
        if value.state == PreparationTaskExecutionState.IN_PROGRESS
    )
    ordered_events = [value.model_dump(mode="json") for value in overview.events]
    ledger_hash = execution_event_ledger_hash(ordered_events)
    latest_event_id = overview.events[-1].id if overview.events else None
    captured_at = utcnow().isoformat()

    candidate = PreparationExecutionSnapshot.model_construct(
        snapshot_version=EXECUTION_SNAPSHOT_VERSION,
        source_schedule_id=overview.schedule.id,
        source_schedule_version=overview.schedule.version,
        latest_execution_event_id=latest_event_id,
        execution_event_count=len(overview.events),
        execution_event_ledger_hash=ledger_hash,
        task_states=task_states,
        frozen_task_ids=frozen,
        repairable_task_ids=repairable,
        in_progress_task_ids=in_progress,
        captured_at=captured_at,
        execution_snapshot_hash="0" * 64,
    )
    snapshot_hash = preparation_execution_snapshot_hash(candidate)
    return PreparationExecutionSnapshot(
        **candidate.model_dump(mode="json", exclude={"execution_snapshot_hash"}),
        execution_snapshot_hash=snapshot_hash,
    )


def assert_preparation_execution_snapshot_unchanged(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    expected_execution_snapshot_hash: str,
) -> PreparationExecutionSnapshot:
    """Fail closed when any source execution event or task state changed."""

    observed = get_preparation_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    if observed.execution_snapshot_hash != expected_execution_snapshot_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_execution_snapshot_changed",
                "message": (
                    "Source task execution changed after the repair snapshot was captured"
                ),
                "expected_execution_snapshot_hash": expected_execution_snapshot_hash,
                "observed_execution_snapshot_hash": observed.execution_snapshot_hash,
                "observed_latest_execution_event_id": (
                    observed.latest_execution_event_id
                ),
                "observed_execution_event_count": observed.execution_event_count,
            },
        )
    return observed


def assert_execution_aware_supersession_allowed(
    snapshot: PreparationExecutionSnapshot,
) -> None:
    """Prevent superseding a source while a task is actively in progress."""

    if snapshot.in_progress_task_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_execution_snapshot_has_in_progress_tasks",
                "message": (
                    "Execution-aware replacement cannot supersede a schedule while "
                    "a source task is in progress"
                ),
                "in_progress_task_ids": snapshot.in_progress_task_ids,
            },
        )


def get_accepted_preparation_repair_task_lineage(
    db: Session,
    *,
    household_id: str,
    proposal_id: int,
) -> PreparationRepairTaskLineage:
    """Return deterministic source→replacement lineage for one accepted proposal.

    Arbitrary schedule pairs are deliberately unsupported. The accepted proposal
    and acceptance row establish the source/replacement relationship, while the
    canonical execution snapshot supplies historical task state. This endpoint is
    read-only evidence; it never supersedes schedules or copies execution events.
    """

    proposal = (
        db.query(DBPreparationRepairProposal)
        .filter(
            DBPreparationRepairProposal.id == proposal_id,
            DBPreparationRepairProposal.household_id == household_id,
        )
        .first()
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    acceptance = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.proposal_id == proposal.id,
            DBPreparationRepairProposalAcceptance.household_id == household_id,
        )
        .first()
    )
    if acceptance is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_task_lineage_requires_accepted_replacement",
                "message": (
                    "Task lineage is authoritative only after a repair proposal "
                    "creates its replacement draft"
                ),
                "proposal_id": proposal.id,
            },
        )

    if (
        acceptance.source_schedule_id != proposal.source_schedule_id
        or acceptance.source_schedule_version != proposal.source_schedule_version
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_task_lineage_acceptance_identity_mismatch",
                "message": "Accepted repair source identity no longer matches proposal",
                "proposal_id": proposal.id,
            },
        )

    source = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == proposal.source_schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    replacement = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == acceptance.created_schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .first()
    )
    if source is None or replacement is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if (
        replacement.source_repair_proposal_id != proposal.id
        or replacement.source_repair_proposal_version
        != acceptance.proposal_version_after
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_task_lineage_replacement_identity_mismatch",
                "message": "Replacement schedule no longer matches acceptance lineage",
                "proposal_id": proposal.id,
                "replacement_schedule_id": replacement.id,
            },
        )

    snapshot = get_preparation_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=source.id,
    )
    if snapshot.source_schedule_version != proposal.source_schedule_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_task_lineage_source_version_changed",
                "message": "Source schedule execution identity changed after acceptance",
                "expected_source_schedule_version": proposal.source_schedule_version,
                "observed_source_schedule_version": snapshot.source_schedule_version,
            },
        )

    try:
        source_schedule = PreparationScheduleResponse.model_validate(
            source.schedule_payload
        )
        replacement_schedule = PreparationScheduleResponse.model_validate(
            replacement.schedule_payload
        )
        return derive_preparation_repair_task_lineage(
            execution_snapshot=snapshot,
            source_schedule=source_schedule,
            replacement_schedule=replacement_schedule,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "repair_task_lineage_not_derivable",
                "message": str(exc),
                "proposal_id": proposal.id,
            },
        ) from exc


__all__ = [
    "assert_execution_aware_supersession_allowed",
    "assert_preparation_execution_snapshot_unchanged",
    "get_accepted_preparation_repair_task_lineage",
    "get_preparation_execution_snapshot",
]
