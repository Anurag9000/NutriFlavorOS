from __future__ import annotations

import pytest

import backend.services.preparation_execution_aware_repair_snapshot_service as rich_snapshot_service
from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
)
from backend.services.preparation_execution_aware_repair_snapshot_service import (
    build_execution_aware_repair_snapshot,
)
from backend.services.preparation_execution_snapshot_service import (
    get_preparation_execution_snapshot,
)
from backend.services.preparation_operations_service import transition_schedule
from backend.services.preparation_task_execution_service import record_task_execution_event
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    db,
)


def _approved_schedule(db):
    calendar = create_calendar(db)
    source = create_schedule(db, calendar)
    return transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=ScheduleStateTransitionRequest.model_validate(
            {
                "expected_version": source.version,
                "reason": "Approve source for execution snapshot binding test",
                "idempotency_key": "execution-aware-binding-approve",
                "metadata": {"test": "canonical-rich-binding"},
            }
        ),
    )


def test_rich_snapshot_is_bound_to_canonical_execution_identity(db):
    calendar = create_calendar(db)
    source = create_schedule(db, calendar)

    canonical = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )
    rich = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )

    assert rich.canonical_execution_snapshot_hash == canonical.execution_snapshot_hash
    assert len(rich.canonical_execution_snapshot_hash) == 64
    assert rich.event_count == canonical.execution_event_count == 0
    assert rich.event_ids == []
    assert set(rich.terminal_task_ids) == set(canonical.frozen_task_ids)
    assert set(rich.active_task_ids) == set(canonical.in_progress_task_ids)
    assert set(rich.repairable_task_ids) == set(canonical.repairable_task_ids)
    assert set(rich.frozen_task_ids) == (
        set(canonical.frozen_task_ids) | set(canonical.in_progress_task_ids)
    )
    assert {
        value.task_id: (value.state, value.latest_event_id) for value in rich.tasks
    } == {
        value.task_id: (value.state, value.latest_event_id)
        for value in canonical.task_states
    }


def test_execution_event_changes_both_canonical_and_rich_snapshot_hashes(db):
    source = _approved_schedule(db)
    before_canonical = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )
    before_rich = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )
    task = next(value for value in source.schedule.scheduled if not value.dependencies)

    mutation = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=PreparationTaskExecutionEventCreate.model_validate(
            {
                "expected_schedule_version": source.version,
                "actual_minute": task.start_minute,
                "reason": "Start task to advance canonical execution identity",
                "notes": None,
                "idempotency_key": "execution-aware-binding-start",
                "metadata": {"test": "canonical-rich-binding"},
            }
        ),
    )

    after_canonical = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )
    after_rich = build_execution_aware_repair_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )

    assert mutation.event.id == after_canonical.latest_execution_event_id
    assert before_canonical.execution_snapshot_hash != after_canonical.execution_snapshot_hash
    assert before_rich.snapshot_hash != after_rich.snapshot_hash
    assert after_rich.canonical_execution_snapshot_hash == (
        after_canonical.execution_snapshot_hash
    )
    assert task.task_id in after_rich.active_task_ids
    assert task.task_id in after_rich.frozen_task_ids
    assert task.task_id not in after_rich.repairable_task_ids


def test_rich_snapshot_fails_closed_when_canonical_partition_disagrees(db, monkeypatch):
    calendar = create_calendar(db)
    source = create_schedule(db, calendar)
    canonical = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )
    mismatched = canonical.model_copy(update={"repairable_task_ids": []})

    monkeypatch.setattr(
        rich_snapshot_service,
        "get_preparation_execution_snapshot",
        lambda *args, **kwargs: mismatched,
    )

    with pytest.raises(ValueError, match="canonical execution snapshot mismatch") as exc:
        build_execution_aware_repair_snapshot(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=source.id,
        )

    assert "repairable partition" in str(exc.value)


def test_rich_snapshot_fails_closed_when_canonical_task_identity_disagrees(db, monkeypatch):
    calendar = create_calendar(db)
    source = create_schedule(db, calendar)
    canonical = get_preparation_execution_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )
    mismatched = canonical.model_copy(update={"task_states": canonical.task_states[:-1]})

    monkeypatch.setattr(
        rich_snapshot_service,
        "get_preparation_execution_snapshot",
        lambda *args, **kwargs: mismatched,
    )

    with pytest.raises(ValueError, match="canonical execution snapshot mismatch") as exc:
        build_execution_aware_repair_snapshot(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=source.id,
        )

    assert "task identity set" in str(exc.value)
