"""Deterministic task-lineage contracts for execution-aware preparation repair."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field, model_validator

from backend.domain.preparation import PreparationScheduleResponse, ScheduledPreparationTask
from backend.domain.preparation_execution_snapshot import (
    PreparationExecutionSnapshot,
    PreparationRepairTaskLineageStatus,
)
from backend.domain.preparation_operations import StrictPreparationOperationsModel
from backend.domain.preparation_task_execution import PreparationTaskExecutionState


class PreparationRepairTaskLineageEntry(StrictPreparationOperationsModel):
    source_task_id: Optional[str] = Field(default=None, min_length=1, max_length=160)
    replacement_task_id: Optional[str] = Field(default=None, min_length=1, max_length=160)
    status: PreparationRepairTaskLineageStatus
    source_execution_state: Optional[PreparationTaskExecutionState] = None
    source_latest_event_id: Optional[int] = Field(default=None, ge=1)
    source_start_minute: Optional[int] = Field(default=None, ge=0)
    source_finish_minute: Optional[int] = Field(default=None, ge=0)
    replacement_start_minute: Optional[int] = Field(default=None, ge=0)
    replacement_finish_minute: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_identity(self):
        if self.source_task_id is None and self.replacement_task_id is None:
            raise ValueError("task lineage entry requires a source or replacement task")
        if self.status == PreparationRepairTaskLineageStatus.NEWLY_INTRODUCED:
            if self.source_task_id is not None or self.replacement_task_id is None:
                raise ValueError("newly introduced lineage requires replacement-only identity")
        elif self.source_task_id is None:
            raise ValueError("non-introduced lineage requires a source task")
        return self


class PreparationRepairTaskLineage(StrictPreparationOperationsModel):
    source_schedule_id: int = Field(ge=1)
    source_schedule_version: int = Field(ge=1)
    source_execution_snapshot_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    entries: List[PreparationRepairTaskLineageEntry]

    @model_validator(mode="after")
    def validate_unique_identities(self):
        source_ids = [value.source_task_id for value in self.entries if value.source_task_id]
        replacement_ids = [
            value.replacement_task_id
            for value in self.entries
            if value.replacement_task_id
        ]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source task IDs must appear once in repair lineage")
        if len(replacement_ids) != len(set(replacement_ids)):
            raise ValueError("replacement task IDs must appear once in repair lineage")
        return self


def _structural_task_identity(task: ScheduledPreparationTask) -> dict:
    """Return task identity excluding schedule position only."""

    return {
        "task_id": task.task_id,
        "duration_minutes": task.duration_minutes,
        "priority": task.priority,
        "resource_demands": task.resource_demands,
        "dependencies": task.dependencies,
        "metadata": task.metadata,
    }


def derive_preparation_repair_task_lineage(
    *,
    execution_snapshot: PreparationExecutionSnapshot,
    source_schedule: PreparationScheduleResponse,
    replacement_schedule: PreparationScheduleResponse,
) -> PreparationRepairTaskLineage:
    """Classify every source/replacement task without copying execution events.

    Executed terminal source tasks are historical facts. They are represented as
    ``frozen_by_execution`` and MUST NOT be present as executable replacement
    tasks. In-progress source work blocks supersession before lineage can become
    authoritative. Planned source work may be preserved, shifted, structurally
    superseded, or removed before execution. Replacement-only work is explicit.
    """

    if execution_snapshot.in_progress_task_ids:
        raise ValueError(
            "cannot derive authoritative replacement lineage while source tasks "
            "are in progress: "
            + ", ".join(execution_snapshot.in_progress_task_ids)
        )

    source_by_id = {value.task_id: value for value in source_schedule.scheduled}
    replacement_by_id = {
        value.task_id: value for value in replacement_schedule.scheduled
    }
    snapshot_by_id = {value.task_id: value for value in execution_snapshot.task_states}

    if set(source_by_id) != set(snapshot_by_id):
        missing_snapshot = sorted(set(source_by_id) - set(snapshot_by_id))
        unknown_snapshot = sorted(set(snapshot_by_id) - set(source_by_id))
        raise ValueError(
            "execution snapshot/source schedule task identity mismatch; "
            f"missing_snapshot={missing_snapshot}; unknown_snapshot={unknown_snapshot}"
        )

    duplicated_terminal = sorted(
        set(execution_snapshot.frozen_task_ids) & set(replacement_by_id)
    )
    if duplicated_terminal:
        raise ValueError(
            "replacement schedule cannot reintroduce terminal source tasks: "
            + ", ".join(duplicated_terminal)
        )

    entries: list[PreparationRepairTaskLineageEntry] = []
    for task_id in sorted(source_by_id):
        source_task = source_by_id[task_id]
        snapshot_task = snapshot_by_id[task_id]
        replacement_task = replacement_by_id.get(task_id)

        if task_id in execution_snapshot.frozen_task_ids:
            status = PreparationRepairTaskLineageStatus.FROZEN_BY_EXECUTION
        elif replacement_task is None:
            status = PreparationRepairTaskLineageStatus.REMOVED_BEFORE_EXECUTION
        elif source_task.model_dump(mode="json") == replacement_task.model_dump(mode="json"):
            status = PreparationRepairTaskLineageStatus.PRESERVED
        elif _structural_task_identity(source_task) == _structural_task_identity(
            replacement_task
        ):
            status = PreparationRepairTaskLineageStatus.SHIFTED
        else:
            status = PreparationRepairTaskLineageStatus.SUPERSEDED_BY_REPLACEMENT

        entries.append(
            PreparationRepairTaskLineageEntry(
                source_task_id=task_id,
                replacement_task_id=(
                    replacement_task.task_id if replacement_task is not None else None
                ),
                status=status,
                source_execution_state=snapshot_task.state,
                source_latest_event_id=snapshot_task.latest_event_id,
                source_start_minute=source_task.start_minute,
                source_finish_minute=source_task.finish_minute,
                replacement_start_minute=(
                    replacement_task.start_minute
                    if replacement_task is not None
                    else None
                ),
                replacement_finish_minute=(
                    replacement_task.finish_minute
                    if replacement_task is not None
                    else None
                ),
            )
        )

    for task_id in sorted(set(replacement_by_id) - set(source_by_id)):
        replacement_task = replacement_by_id[task_id]
        entries.append(
            PreparationRepairTaskLineageEntry(
                source_task_id=None,
                replacement_task_id=task_id,
                status=PreparationRepairTaskLineageStatus.NEWLY_INTRODUCED,
                source_execution_state=None,
                source_latest_event_id=None,
                source_start_minute=None,
                source_finish_minute=None,
                replacement_start_minute=replacement_task.start_minute,
                replacement_finish_minute=replacement_task.finish_minute,
            )
        )

    entries.sort(
        key=lambda value: (
            value.source_task_id is None,
            value.source_task_id or value.replacement_task_id or "",
        )
    )
    return PreparationRepairTaskLineage(
        source_schedule_id=execution_snapshot.source_schedule_id,
        source_schedule_version=execution_snapshot.source_schedule_version,
        source_execution_snapshot_hash=execution_snapshot.execution_snapshot_hash,
        entries=entries,
    )


__all__ = [
    "PreparationRepairTaskLineage",
    "PreparationRepairTaskLineageEntry",
    "derive_preparation_repair_task_lineage",
]
