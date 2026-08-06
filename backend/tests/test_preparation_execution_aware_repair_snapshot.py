from __future__ import annotations

from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionState,
)
from backend.services.preparation_execution_aware_repair_snapshot_service import (
    build_execution_aware_repair_snapshot,
)
from backend.services.preparation_task_execution_authoritative_service import (
    get_task_execution_overview,
    record_task_execution_event,
)
from backend.tests.test_preparation_operations_service import HOUSEHOLD_ID, OWNER_ID
from backend.tests.test_preparation_task_execution_service import (
    create_approved_schedule,
    db,
    event_payload,
)


def _ordered_tasks(db, schedule_id: int):
    overview = get_task_execution_overview(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule_id,
    )
    return sorted(
        (value.task for value in overview.tasks),
        key=lambda value: (value.start_minute, value.finish_minute, value.task_id),
    )


def test_snapshot_is_deterministic_and_partitions_unexecuted_work(db):
    approved = create_approved_schedule(db)

    first = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    repeated = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )

    expected = sorted(value.task_id for value in approved.schedule.scheduled)
    assert first.snapshot_hash == repeated.snapshot_hash
    assert first.event_count == 0
    assert first.event_ids == []
    assert first.event_chain_hash == repeated.event_chain_hash
    assert first.frozen_task_ids == []
    assert first.active_task_ids == []
    assert first.terminal_task_ids == []
    assert first.repairable_task_ids == expected
    assert first.ready_repairable_task_ids == ["dinner.prep"]
    assert first.blocked_repairable_tasks == {
        "dinner.cook": ["dinner.prep"],
    }
    assert first.repair_computation_performed is False
    assert first.persistence_performed is False
    assert first.requires_human_acceptance is True


def test_started_task_is_frozen_and_blocks_dependent_repair_frontier(db):
    approved = create_approved_schedule(db)
    prep, cook = _ordered_tasks(db, approved.id)

    started = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=prep.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            prep.start_minute + 5,
            "snapshot-started-prep",
            reason="Household began preparation five minutes late",
        ),
    )
    snapshot = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        for_update=True,
    )

    assert snapshot.source_schedule_version == started.schedule.version
    assert snapshot.event_count == 1
    assert snapshot.active_task_ids == [prep.task_id]
    assert snapshot.frozen_task_ids == [prep.task_id]
    assert snapshot.terminal_task_ids == []
    assert snapshot.repairable_task_ids == [cook.task_id]
    assert snapshot.ready_repairable_task_ids == []
    assert snapshot.blocked_repairable_tasks == {cook.task_id: [prep.task_id]}
    prep_evidence = next(value for value in snapshot.tasks if value.task_id == prep.task_id)
    assert prep_evidence.state == PreparationTaskExecutionState.IN_PROGRESS
    assert prep_evidence.confirmed_start_minute == prep.start_minute + 5
    assert prep_evidence.frozen is True
    assert prep_evidence.repairable is False


def test_completed_task_satisfies_dependency_and_changes_snapshot_hash(db):
    approved = create_approved_schedule(db)
    prep, cook = _ordered_tasks(db, approved.id)
    initial = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )

    started = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=prep.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=event_payload(
            approved.version,
            prep.start_minute,
            "snapshot-completion-start",
        ),
    )
    completed = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=prep.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.COMPLETED,
        payload=event_payload(
            started.schedule.version,
            prep.finish_minute + 3,
            "snapshot-completion-finish",
            reason="Preparation completed three minutes late",
        ),
    )
    snapshot = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )

    assert snapshot.snapshot_hash != initial.snapshot_hash
    assert snapshot.event_chain_hash != initial.event_chain_hash
    assert snapshot.source_schedule_version == completed.schedule.version
    assert snapshot.event_count == 2
    assert snapshot.active_task_ids == []
    assert snapshot.terminal_task_ids == [prep.task_id]
    assert snapshot.satisfied_dependency_task_ids == [prep.task_id]
    assert snapshot.repairable_task_ids == [cook.task_id]
    assert snapshot.ready_repairable_task_ids == [cook.task_id]
    assert snapshot.blocked_repairable_tasks == {}
    evidence = next(value for value in snapshot.tasks if value.task_id == prep.task_id)
    assert evidence.state == PreparationTaskExecutionState.COMPLETED
    assert evidence.confirmed_start_minute == prep.start_minute
    assert evidence.confirmed_terminal_minute == prep.finish_minute + 3
    assert evidence.terminal_event_type == "completed"


def test_skipped_task_is_terminal_without_fabricating_a_start(db):
    approved = create_approved_schedule(db)
    prep, cook = _ordered_tasks(db, approved.id)
    skipped = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
        task_id=prep.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.SKIPPED,
        payload=event_payload(
            approved.version,
            prep.start_minute,
            "snapshot-skipped-prep",
            reason="Household explicitly skipped preparation",
        ),
    )

    snapshot = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=approved.id,
    )
    evidence = next(value for value in snapshot.tasks if value.task_id == prep.task_id)

    assert snapshot.source_schedule_version == skipped.schedule.version
    assert snapshot.terminal_task_ids == [prep.task_id]
    assert snapshot.ready_repairable_task_ids == [cook.task_id]
    assert evidence.state == PreparationTaskExecutionState.SKIPPED
    assert evidence.confirmed_start_minute is None
    assert evidence.confirmed_terminal_minute == prep.start_minute
    assert evidence.terminal_event_type == "skipped"
    assert evidence.terminal_reason == "Household explicitly skipped preparation"
