"""Fail-closed preflight for future execution-aware repair proposal mutation.

The service proves that a caller is reasoning from the exact current execution
frontier, preserves every started/terminal task byte-for-byte, normalizes
terminal dependencies out of future work, and withholds every planned task that
still depends (directly or transitively) on in-progress work. It deliberately
performs no repair computation and no persistence.
"""

from __future__ import annotations

from typing import Dict, Set

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.domain.preparation import PreparationScheduleRequest, PreparationTask
from backend.domain.preparation_execution_aware_repair import (
    PreparationExecutionAwareRepairSnapshot,
)
from backend.domain.preparation_execution_aware_repair_proposals import (
    PreparationExecutionAwareRepairPreflightView,
    PreparationExecutionAwareRepairProposalCreateRequest,
)
from backend.services.household_plan_lifecycle_service import assert_approved_source_plan
from backend.services.preparation_execution_aware_repair_snapshot_service import (
    build_execution_aware_repair_snapshot,
)
from backend.services.preparation_operations_service import _assert_schedule_matches_calendar
from backend.services.preparation_repair_proposal_service import (
    ACTIVE_SOURCE_STATUSES,
    _load_source_payloads,
    _source_schedule,
    _target_calendar,
)


_LIMITATIONS = [
    "Preflight does not persist a repair proposal or replacement schedule.",
    "Preflight does not run the repair scheduler or imply that a future candidate is feasible.",
    "Task additions and removals remain disabled until introduced/removed-task provenance is persisted explicitly.",
    "Started and terminal task definitions are immutable execution history.",
    "Planned descendants of in-progress tasks are withheld until that work becomes terminal.",
    "Terminal dependencies are treated as satisfied by the existing execution authority and removed from the normalized future request.",
    "Any later proposal mutation must re-lock the household/source and revalidate the exact canonical execution snapshot hash.",
    "Any accepted replacement still requires explicit human acceptance and separate owner approval.",
]


def _conflict(code: str, message: str, **details: object) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": message, **details},
    )


def _task_map(request: PreparationScheduleRequest) -> Dict[str, PreparationTask]:
    return {task.task_id: task for task in request.tasks}


def _active_ancestors_by_task(
    *,
    graph: Dict[str, tuple[str, ...]],
    active_task_ids: Set[str],
) -> Dict[str, Set[str]]:
    memo: Dict[str, Set[str]] = {}

    def visit(task_id: str) -> Set[str]:
        existing = memo.get(task_id)
        if existing is not None:
            return existing
        ancestors: Set[str] = set()
        for dependency in graph[task_id]:
            if dependency in active_task_ids:
                ancestors.add(dependency)
            ancestors.update(visit(dependency))
        memo[task_id] = ancestors
        return ancestors

    for task_id in graph:
        visit(task_id)
    return memo


def preflight_execution_aware_repair_request(
    *,
    snapshot: PreparationExecutionAwareRepairSnapshot,
    source_request: PreparationScheduleRequest,
    payload: PreparationExecutionAwareRepairProposalCreateRequest,
) -> PreparationExecutionAwareRepairPreflightView:
    """Validate and normalize one exact execution-aware future-work request."""

    identity_pairs = (
        ("source_schedule_id", payload.source_schedule_id, snapshot.source_schedule_id),
        (
            "source_schedule_version",
            payload.expected_source_version,
            snapshot.source_schedule_version,
        ),
        (
            "source_schedule_hash",
            payload.expected_source_schedule_hash,
            snapshot.source_schedule_hash,
        ),
        (
            "execution_snapshot_hash",
            payload.expected_execution_snapshot_hash,
            snapshot.canonical_execution_snapshot_hash,
        ),
        (
            "execution_aware_snapshot_hash",
            payload.expected_execution_aware_snapshot_hash,
            snapshot.snapshot_hash,
        ),
    )
    for field, expected, observed in identity_pairs:
        if expected != observed:
            raise _conflict(
                "execution_aware_repair_snapshot_changed",
                f"Execution-aware repair {field} changed before preflight",
                field=field,
                expected=expected,
                observed=observed,
            )

    if snapshot.event_count == 0:
        raise _conflict(
            "execution_aware_repair_requires_execution_history",
            "Use ordinary repair when the source has no task execution history",
            source_schedule_id=snapshot.source_schedule_id,
        )

    source_tasks = _task_map(source_request)
    revised_tasks = _task_map(payload.revised_request)
    snapshot_ids = {task.task_id for task in snapshot.tasks}
    source_ids = set(source_tasks)
    revised_ids = set(revised_tasks)
    if snapshot_ids != source_ids:
        raise _conflict(
            "execution_aware_repair_source_snapshot_task_mismatch",
            "Source request task identity differs from the execution snapshot",
            source_only=sorted(source_ids - snapshot_ids),
            snapshot_only=sorted(snapshot_ids - source_ids),
        )
    if revised_ids != source_ids:
        raise _conflict(
            "execution_aware_repair_task_identity_change_not_enabled",
            "Execution-aware preflight does not yet allow task additions or removals",
            added_task_ids=sorted(revised_ids - source_ids),
            removed_task_ids=sorted(source_ids - revised_ids),
        )

    if (
        payload.revised_request.horizon_minutes != source_request.horizon_minutes
        or payload.revised_request.granularity_minutes
        != source_request.granularity_minutes
    ):
        raise _conflict(
            "execution_aware_repair_global_timebase_changed",
            "Execution history is bound to the source horizon and granularity",
            source_horizon_minutes=source_request.horizon_minutes,
            revised_horizon_minutes=payload.revised_request.horizon_minutes,
            source_granularity_minutes=source_request.granularity_minutes,
            revised_granularity_minutes=payload.revised_request.granularity_minutes,
        )

    frozen_ids = set(snapshot.frozen_task_ids)
    terminal_ids = set(snapshot.terminal_task_ids)
    active_ids = set(snapshot.active_task_ids)
    repairable_ids = set(snapshot.repairable_task_ids)
    for task_id in sorted(frozen_ids):
        source_payload = source_tasks[task_id].model_dump(mode="json")
        revised_payload = revised_tasks[task_id].model_dump(mode="json")
        if source_payload != revised_payload:
            raise _conflict(
                "execution_aware_repair_frozen_task_changed",
                "Started or terminal task definitions are immutable",
                task_id=task_id,
                execution_state=(
                    "in_progress" if task_id in active_ids else "terminal"
                ),
            )

    graph = {
        task_id: tuple(revised_tasks[task_id].dependencies)
        for task_id in sorted(revised_tasks)
    }
    active_ancestors = _active_ancestors_by_task(
        graph=graph,
        active_task_ids=active_ids,
    )
    blocked_by_active = {
        task_id: sorted(active_ancestors[task_id])
        for task_id in sorted(repairable_ids)
        if active_ancestors[task_id]
    }
    candidate_ids = sorted(repairable_ids - set(blocked_by_active))
    candidate_set = set(candidate_ids)

    normalized_tasks = []
    for task_id in candidate_ids:
        task_payload = revised_tasks[task_id].model_dump(mode="json")
        dependencies = [
            dependency
            for dependency in task_payload.get("dependencies", [])
            if dependency not in terminal_ids
        ]
        unknown_future_dependency = sorted(set(dependencies) - candidate_set)
        if unknown_future_dependency:
            raise _conflict(
                "execution_aware_repair_future_dependency_not_candidate",
                "Future repair task depends on work outside the executable candidate frontier",
                task_id=task_id,
                dependency_task_ids=unknown_future_dependency,
            )
        task_payload["dependencies"] = dependencies
        normalized_tasks.append(task_payload)

    normalized_future = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": payload.revised_request.horizon_minutes,
            "granularity_minutes": payload.revised_request.granularity_minutes,
            "resources": [
                resource.model_dump(mode="json")
                for resource in payload.revised_request.resources
            ],
            "tasks": normalized_tasks,
        }
    )
    return PreparationExecutionAwareRepairPreflightView(
        source_schedule_id=snapshot.source_schedule_id,
        source_schedule_version=snapshot.source_schedule_version,
        source_schedule_hash=snapshot.source_schedule_hash,
        canonical_execution_snapshot_hash=snapshot.canonical_execution_snapshot_hash,
        execution_aware_snapshot_hash=snapshot.snapshot_hash,
        target_calendar_version_id=payload.target_calendar_version_id,
        frozen_task_ids=sorted(frozen_ids),
        terminal_task_ids=sorted(terminal_ids),
        in_progress_task_ids=sorted(active_ids),
        repairable_task_ids=sorted(repairable_ids),
        blocked_by_in_progress_task_ids=blocked_by_active,
        candidate_task_ids=candidate_ids,
        normalized_future_request=normalized_future,
        ready_for_proposal_computation=bool(candidate_ids),
        requires_human_acceptance=True,
        repair_computation_performed=False,
        proposal_persistence_performed=False,
        schedule_persistence_performed=False,
        limitations=_LIMITATIONS,
    )


def preflight_execution_aware_repair_proposal(
    db: Session,
    *,
    household_id: str,
    payload: PreparationExecutionAwareRepairProposalCreateRequest,
) -> PreparationExecutionAwareRepairPreflightView:
    """Load locked authoritative evidence and return a non-persistent preflight."""

    source = _source_schedule(
        db,
        household_id=household_id,
        schedule_id=payload.source_schedule_id,
        for_update=True,
    )
    if source.status not in ACTIVE_SOURCE_STATUSES:
        raise _conflict(
            "execution_aware_repair_source_status_not_supported",
            "Only replayable draft or approved schedules can be preflighted",
            status=source.status,
        )
    if source.version != payload.expected_source_version:
        raise _conflict(
            "execution_aware_repair_snapshot_changed",
            "Source schedule version changed before preflight",
            field="source_schedule_version",
            expected=payload.expected_source_version,
            observed=source.version,
        )
    if source.schedule_hash != payload.expected_source_schedule_hash:
        raise _conflict(
            "execution_aware_repair_snapshot_changed",
            "Source schedule hash changed before preflight",
            field="source_schedule_hash",
            expected=payload.expected_source_schedule_hash,
            observed=source.schedule_hash,
        )

    _, source_request, _ = _load_source_payloads(source)
    assert_approved_source_plan(
        db,
        household_id=household_id,
        source_plan_id=source.source_plan_id,
        source_plan_version=source.source_plan_version,
    )
    snapshot = build_execution_aware_repair_snapshot(
        db,
        household_id=household_id,
        schedule_id=source.id,
        for_update=True,
    )
    preflight = preflight_execution_aware_repair_request(
        snapshot=snapshot,
        source_request=source_request,
        payload=payload,
    )
    calendar = _target_calendar(
        db,
        household_id=household_id,
        calendar_id=payload.target_calendar_version_id,
        for_update=True,
    )
    _assert_schedule_matches_calendar(
        db,
        calendar,
        preflight.normalized_future_request,
    )
    return preflight


__all__ = [
    "preflight_execution_aware_repair_proposal",
    "preflight_execution_aware_repair_request",
]
