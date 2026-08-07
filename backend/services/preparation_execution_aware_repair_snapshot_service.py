"""Build canonical execution evidence for future execution-aware repair.

The richer snapshot is deliberately read-only. It freezes every task with
confirmed execution history, identifies the planned repair frontier, and hashes
the full validated event chain without exposing raw idempotency keys. Its
identity is cryptographically bound to the canonical execution snapshot used by
proposal mutation guards so the repository has one execution-state authority.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Dict, List

from sqlalchemy.orm import Session

from backend.domain.preparation_execution_aware_repair import (
    PreparationExecutionAwareRepairSnapshot,
    PreparationExecutionAwareTaskEvidence,
)
from backend.domain.preparation_execution_snapshot import PreparationExecutionSnapshot
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventType,
    PreparationTaskExecutionState,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_task_execution_models import DBPreparationTaskExecutionEvent
from backend.services.preparation_execution_snapshot_service import (
    get_preparation_execution_snapshot,
)
from backend.services.preparation_operations_service import _lock_household
from backend.services.preparation_task_execution_authoritative_service import (
    validate_task_execution_snapshot,
)


_LIMITATIONS = [
    "This snapshot does not compute or persist a repaired schedule.",
    "In-progress and terminal tasks are frozen; their confirmed effects are not reversible.",
    "This richer projection is bound to the canonical execution snapshot used by mutation guards.",
    "A later repair mutation must lock the household and source schedule and revalidate the canonical snapshot hash.",
    "Inventory, leftovers, shopping, appliance state, food safety, and human presence are outside this snapshot.",
    "Any future replacement still requires explicit human acceptance and separate owner approval.",
]


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _lock_schedule(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> None:
    _lock_household(db, household_id)
    (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.id == schedule_id,
            DBPersistedPreparationSchedule.household_id == household_id,
        )
        .with_for_update()
        .one_or_none()
    )


def _event_chain_payload(
    events: List[DBPreparationTaskExecutionEvent],
) -> List[dict]:
    return [
        {
            "id": value.id,
            "schedule_id": value.schedule_id,
            "household_id": value.household_id,
            "task_id": value.task_id,
            "event_type": value.event_type,
            "actor_user_id": value.actor_user_id,
            "from_state": value.from_state,
            "to_state": value.to_state,
            "planned_start_minute": value.planned_start_minute,
            "planned_finish_minute": value.planned_finish_minute,
            "actual_minute": value.actual_minute,
            "deviation_minutes": value.deviation_minutes,
            "reason": value.reason,
            "notes": value.notes,
            "metadata": dict(value.event_metadata or {}),
            "idempotency_key_hash": _canonical_hash(value.idempotency_key),
            "request_fingerprint": value.request_fingerprint,
            "schedule_version_before": value.schedule_version_before,
            "schedule_version_after": value.schedule_version_after,
            "created_at": value.created_at.isoformat(),
        }
        for value in events
    ]


def _assert_canonical_snapshot_correspondence(
    canonical: PreparationExecutionSnapshot,
    *,
    schedule: DBPersistedPreparationSchedule,
    events: List[DBPreparationTaskExecutionEvent],
    evidence: List[PreparationExecutionAwareTaskEvidence],
    terminal_ids: List[str],
    active_ids: List[str],
    frozen_ids: List[str],
    repairable_ids: List[str],
) -> None:
    """Fail closed if richer evidence diverges from canonical mutation authority."""

    errors: list[str] = []
    if canonical.source_schedule_id != schedule.id:
        errors.append("source schedule ID")
    if canonical.source_schedule_version != schedule.version:
        errors.append("source schedule version")
    if canonical.execution_event_count != len(events):
        errors.append("execution event count")
    expected_latest = events[-1].id if events else None
    if canonical.latest_execution_event_id != expected_latest:
        errors.append("latest execution event ID")

    canonical_by_id = {value.task_id: value for value in canonical.task_states}
    rich_by_id = {value.task_id: value for value in evidence}
    if set(canonical_by_id) != set(rich_by_id):
        errors.append("task identity set")
    else:
        for task_id in sorted(canonical_by_id):
            canonical_task = canonical_by_id[task_id]
            rich_task = rich_by_id[task_id]
            if canonical_task.state != rich_task.state:
                errors.append(f"task state:{task_id}")
            if canonical_task.latest_event_id != rich_task.latest_event_id:
                errors.append(f"task latest event:{task_id}")

    # Canonical `frozen` means terminal facts only. Richer execution-aware
    # `frozen` additionally includes in-progress work because it cannot move.
    if set(canonical.frozen_task_ids) != set(terminal_ids):
        errors.append("terminal/frozen partition")
    if set(canonical.in_progress_task_ids) != set(active_ids):
        errors.append("in-progress/active partition")
    if set(canonical.repairable_task_ids) != set(repairable_ids):
        errors.append("repairable partition")
    if set(frozen_ids) != set(terminal_ids) | set(active_ids):
        errors.append("rich frozen partition")

    if errors:
        raise ValueError(
            "canonical execution snapshot mismatch: " + ", ".join(sorted(set(errors)))
        )


def build_execution_aware_repair_snapshot(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    for_update: bool = False,
) -> PreparationExecutionAwareRepairSnapshot:
    """Return a deterministic boundary snapshot for one persisted schedule.

    ``for_update=True`` locks the household and source schedule first. Future
    proposal creation must use that mode and compare the caller's expected
    canonical snapshot hash before computing any candidate. Read-only callers
    also fail closed if concurrent activity makes the two projections disagree.
    """

    if for_update:
        _lock_schedule(
            db,
            household_id=household_id,
            schedule_id=schedule_id,
        )
    schedule, tasks, events, states = validate_task_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )

    events_by_task: Dict[str, List[DBPreparationTaskExecutionEvent]] = defaultdict(list)
    for event in events:
        events_by_task[event.task_id].append(event)

    evidence: List[PreparationExecutionAwareTaskEvidence] = []
    for task_id in sorted(tasks):
        task = tasks[task_id]
        state = states[task_id]
        task_events = events_by_task.get(task_id, [])
        started = next(
            (
                value
                for value in task_events
                if value.event_type == PreparationTaskExecutionEventType.STARTED.value
            ),
            None,
        )
        terminal = next(
            (
                value
                for value in reversed(task_events)
                if value.event_type
                in {
                    PreparationTaskExecutionEventType.COMPLETED.value,
                    PreparationTaskExecutionEventType.SKIPPED.value,
                }
            ),
            None,
        )
        latest = task_events[-1] if task_events else None
        is_terminal = state in {
            PreparationTaskExecutionState.COMPLETED,
            PreparationTaskExecutionState.SKIPPED,
        }
        evidence.append(
            PreparationExecutionAwareTaskEvidence(
                task_id=task_id,
                state=state,
                planned_start_minute=task.start_minute,
                planned_finish_minute=task.finish_minute,
                dependencies=sorted(task.dependencies),
                latest_event_id=latest.id if latest else None,
                confirmed_start_minute=started.actual_minute if started else None,
                confirmed_terminal_minute=(
                    terminal.actual_minute if terminal else None
                ),
                terminal_event_type=(terminal.event_type if terminal else None),
                terminal_reason=(terminal.reason if terminal else None),
                frozen=state != PreparationTaskExecutionState.PLANNED,
                terminal=is_terminal,
                repairable=state == PreparationTaskExecutionState.PLANNED,
            )
        )

    terminal_ids = sorted(value.task_id for value in evidence if value.terminal)
    active_ids = sorted(
        value.task_id
        for value in evidence
        if value.state == PreparationTaskExecutionState.IN_PROGRESS
    )
    frozen_ids = sorted(value.task_id for value in evidence if value.frozen)
    repairable_ids = sorted(value.task_id for value in evidence if value.repairable)
    terminal_set = set(terminal_ids)
    blocked: Dict[str, List[str]] = {}
    for task_id in repairable_ids:
        blockers = sorted(
            dependency
            for dependency in tasks[task_id].dependencies
            if dependency not in terminal_set
        )
        if blockers:
            blocked[task_id] = blockers
    ready = sorted(set(repairable_ids) - set(blocked))

    canonical = get_preparation_execution_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    _assert_canonical_snapshot_correspondence(
        canonical,
        schedule=schedule,
        events=events,
        evidence=evidence,
        terminal_ids=terminal_ids,
        active_ids=active_ids,
        frozen_ids=frozen_ids,
        repairable_ids=repairable_ids,
    )

    chain_payload = _event_chain_payload(events)
    event_chain_hash = _canonical_hash(chain_payload)
    snapshot_payload = {
        "household_id": household_id,
        "source_schedule_id": schedule.id,
        "source_schedule_version": schedule.version,
        "source_schedule_status": schedule.status,
        "source_schedule_hash": schedule.schedule_hash,
        "canonical_execution_snapshot_hash": canonical.execution_snapshot_hash,
        "event_count": len(events),
        "event_ids": [value.id for value in events],
        "event_chain_hash": event_chain_hash,
        "tasks": [value.model_dump(mode="json") for value in evidence],
        "frozen_task_ids": frozen_ids,
        "active_task_ids": active_ids,
        "terminal_task_ids": terminal_ids,
        "satisfied_dependency_task_ids": terminal_ids,
        "repairable_task_ids": repairable_ids,
        "ready_repairable_task_ids": ready,
        "blocked_repairable_tasks": blocked,
        "limitations": _LIMITATIONS,
    }
    return PreparationExecutionAwareRepairSnapshot.model_validate(
        {
            **snapshot_payload,
            "first_event_schedule_version": (
                events[0].schedule_version_before if events else None
            ),
            "latest_event_schedule_version": (
                events[-1].schedule_version_after if events else None
            ),
            "snapshot_hash": _canonical_hash(snapshot_payload),
            "requires_human_acceptance": True,
            "repair_computation_performed": False,
            "persistence_performed": False,
        }
    )


__all__ = [
    "_assert_canonical_snapshot_correspondence",
    "build_execution_aware_repair_snapshot",
]
