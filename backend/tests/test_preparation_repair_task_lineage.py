from __future__ import annotations

import pytest

from backend.domain.preparation import (
    PreparationScheduleResponse,
    ScheduledPreparationTask,
)
from backend.domain.preparation_execution_snapshot import (
    EXECUTION_SNAPSHOT_VERSION,
    PreparationExecutionSnapshot,
    PreparationExecutionTaskSnapshot,
    PreparationRepairTaskLineageStatus,
    preparation_execution_snapshot_hash,
)
from backend.domain.preparation_repair_task_lineage import (
    PreparationRepairTaskLineage,
    derive_preparation_repair_task_lineage,
)
from backend.domain.preparation_task_execution import PreparationTaskExecutionState


def _task(
    task_id: str,
    start: int,
    finish: int,
    *,
    priority: int = 0,
) -> ScheduledPreparationTask:
    return ScheduledPreparationTask(
        task_id=task_id,
        start_minute=start,
        finish_minute=finish,
        duration_minutes=finish - start,
        priority=priority,
        resource_demands={"person": 1},
        dependencies=[],
        metadata={"recipe_id": "recipe-1"},
    )


def _schedule(*tasks: ScheduledPreparationTask) -> PreparationScheduleResponse:
    return PreparationScheduleResponse(
        method="deterministic_dependency_aware_resource_scheduler_v2",
        deterministic=True,
        horizon_minutes=120,
        granularity_minutes=5,
        scheduled=list(tasks),
        unscheduled=[],
        resource_utilization={"person": 0.1},
        resource_peak_usage={"person": 1},
        makespan_minutes=max((task.finish_minute for task in tasks), default=0),
        diagnostics={},
    )


def _snapshot(states: list[tuple[str, PreparationTaskExecutionState, int | None]]):
    task_states = sorted(
        [
            PreparationExecutionTaskSnapshot(
                task_id=task_id,
                state=state,
                latest_event_id=event_id,
            )
            for task_id, state, event_id in states
        ],
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
    event_ids = [value.latest_event_id for value in task_states if value.latest_event_id]
    candidate = PreparationExecutionSnapshot.model_construct(
        snapshot_version=EXECUTION_SNAPSHOT_VERSION,
        source_schedule_id=7,
        source_schedule_version=4,
        latest_execution_event_id=max(event_ids) if event_ids else None,
        execution_event_count=len(event_ids),
        execution_event_ledger_hash="a" * 64,
        task_states=task_states,
        frozen_task_ids=frozen,
        repairable_task_ids=repairable,
        in_progress_task_ids=in_progress,
        captured_at="2026-08-07T09:00:00Z",
        execution_snapshot_hash="0" * 64,
    )
    return PreparationExecutionSnapshot(
        **candidate.model_dump(mode="json", exclude={"execution_snapshot_hash"}),
        execution_snapshot_hash=preparation_execution_snapshot_hash(candidate),
    )


def test_lineage_classifies_frozen_preserved_shifted_removed_and_new_tasks():
    source = _schedule(
        _task("done", 0, 10),
        _task("preserved", 10, 20),
        _task("shifted", 20, 30),
        _task("removed", 30, 40),
    )
    replacement = _schedule(
        _task("preserved", 10, 20),
        _task("shifted", 45, 55),
        _task("new", 60, 70),
    )
    snapshot = _snapshot(
        [
            ("done", PreparationTaskExecutionState.COMPLETED, 1),
            ("preserved", PreparationTaskExecutionState.PLANNED, None),
            ("shifted", PreparationTaskExecutionState.PLANNED, None),
            ("removed", PreparationTaskExecutionState.PLANNED, None),
        ]
    )

    lineage = derive_preparation_repair_task_lineage(
        execution_snapshot=snapshot,
        source_schedule=source,
        replacement_schedule=replacement,
    )
    repeated = derive_preparation_repair_task_lineage(
        execution_snapshot=snapshot,
        source_schedule=source,
        replacement_schedule=replacement,
    )
    by_identity = {
        entry.source_task_id or entry.replacement_task_id: entry
        for entry in lineage.entries
    }

    assert lineage.source_schedule_id == 7
    assert lineage.source_schedule_version == 4
    assert lineage.source_execution_snapshot_hash == snapshot.execution_snapshot_hash
    assert len(lineage.lineage_hash) == 64
    assert repeated.lineage_hash == lineage.lineage_hash
    assert by_identity["done"].status == PreparationRepairTaskLineageStatus.FROZEN_BY_EXECUTION
    assert by_identity["done"].replacement_task_id is None
    assert by_identity["preserved"].status == PreparationRepairTaskLineageStatus.PRESERVED
    assert by_identity["shifted"].status == PreparationRepairTaskLineageStatus.SHIFTED
    assert by_identity["removed"].status == PreparationRepairTaskLineageStatus.REMOVED_BEFORE_EXECUTION
    assert by_identity["new"].status == PreparationRepairTaskLineageStatus.NEWLY_INTRODUCED

    tampered = lineage.model_dump(mode="json")
    tampered["lineage_hash"] = "0" * 64
    with pytest.raises(ValueError, match="lineage hash disagrees"):
        PreparationRepairTaskLineage.model_validate(tampered)


def test_lineage_hash_changes_with_replacement_evidence():
    source = _schedule(_task("prep", 10, 20, priority=1))
    snapshot = _snapshot([("prep", PreparationTaskExecutionState.PLANNED, None)])

    first = derive_preparation_repair_task_lineage(
        execution_snapshot=snapshot,
        source_schedule=source,
        replacement_schedule=_schedule(_task("prep", 15, 25, priority=1)),
    )
    second = derive_preparation_repair_task_lineage(
        execution_snapshot=snapshot,
        source_schedule=source,
        replacement_schedule=_schedule(_task("prep", 20, 30, priority=1)),
    )

    assert first.lineage_hash != second.lineage_hash


def test_structural_change_is_explicit_supersession_not_shift():
    source = _schedule(_task("prep", 10, 20, priority=1))
    replacement = _schedule(_task("prep", 15, 25, priority=2))
    snapshot = _snapshot(
        [("prep", PreparationTaskExecutionState.PLANNED, None)]
    )

    lineage = derive_preparation_repair_task_lineage(
        execution_snapshot=snapshot,
        source_schedule=source,
        replacement_schedule=replacement,
    )
    assert lineage.entries[0].status == (
        PreparationRepairTaskLineageStatus.SUPERSEDED_BY_REPLACEMENT
    )


def test_terminal_task_cannot_be_reintroduced_as_executable_replacement():
    source = _schedule(_task("done", 0, 10))
    replacement = _schedule(_task("done", 20, 30))
    snapshot = _snapshot(
        [("done", PreparationTaskExecutionState.COMPLETED, 1)]
    )

    with pytest.raises(ValueError, match="terminal source tasks"):
        derive_preparation_repair_task_lineage(
            execution_snapshot=snapshot,
            source_schedule=source,
            replacement_schedule=replacement,
        )


def test_in_progress_source_blocks_authoritative_lineage():
    source = _schedule(_task("active", 0, 10))
    replacement = _schedule()
    snapshot = _snapshot(
        [("active", PreparationTaskExecutionState.IN_PROGRESS, 1)]
    )

    with pytest.raises(ValueError, match="source tasks are in progress"):
        derive_preparation_repair_task_lineage(
            execution_snapshot=snapshot,
            source_schedule=source,
            replacement_schedule=replacement,
        )


def test_snapshot_must_cover_exact_source_task_set():
    source = _schedule(_task("a", 0, 10), _task("b", 10, 20))
    replacement = _schedule(_task("a", 0, 10))
    snapshot = _snapshot([("a", PreparationTaskExecutionState.PLANNED, None)])

    with pytest.raises(ValueError, match="task identity mismatch"):
        derive_preparation_repair_task_lineage(
            execution_snapshot=snapshot,
            source_schedule=source,
            replacement_schedule=replacement,
        )
