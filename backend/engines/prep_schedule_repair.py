"""Deterministic minimal-change repair for preparation schedules.

The engine never mutates or persists the previous schedule. It pins explicitly
immutable work at its prior deterministic placement, then repairs the remaining
tasks under the revised resources, windows, capacities, dependencies, horizons,
and deadlines. A bounded exact mode provides a small-instance comparator using
the same feasibility semantics.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleRequest,
    PreparationScheduleResponse,
    PreparationTask,
    ScheduledPreparationTask,
    UnscheduledPreparationTask,
)
from backend.domain.preparation_repair import (
    PreparationRepairDiagnostics,
    PreparationRepairObjective,
    PreparationRepairStrategy,
    PreparationScheduleRepairRequest,
    PreparationScheduleRepairResult,
    PreparationTaskMovement,
)


class PreparationRepairError(ValueError):
    """Fail-closed repair error with a stable machine-readable code."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, **self.details}


@dataclass(frozen=True)
class _Placement:
    task: PreparationTask
    start: int
    finish: int


@dataclass
class _SearchCounters:
    explored: int = 0
    pruned: int = 0
    candidates: int = 0
    preserved_attempts: int = 0
    truncated: bool = False


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _task_map(tasks: Sequence[PreparationTask], *, label: str) -> Dict[str, PreparationTask]:
    result: Dict[str, PreparationTask] = {}
    for task in tasks:
        if task.task_id in result:
            raise PreparationRepairError(
                "duplicate_task_id",
                f"{label} contains duplicate task IDs",
                task_id=task.task_id,
            )
        result[task.task_id] = task
    return result


def _scheduled_map(
    response: PreparationScheduleResponse,
    *,
    label: str,
) -> Dict[str, ScheduledPreparationTask]:
    result: Dict[str, ScheduledPreparationTask] = {}
    for task in response.scheduled:
        if task.task_id in result:
            raise PreparationRepairError(
                "duplicate_scheduled_task_id",
                f"{label} contains duplicate scheduled task IDs",
                task_id=task.task_id,
            )
        result[task.task_id] = task
    return result


def _operational_signature(task: PreparationTask) -> tuple:
    return (
        int(task.duration_minutes),
        tuple(sorted((str(key), int(value)) for key, value in task.resource_demands.items())),
        tuple(sorted(task.dependencies)),
    )


def _resource_windows(
    resource: PreparationResource,
    horizon: int,
) -> List[Tuple[int, int]]:
    explicit = getattr(resource, "availability_windows", None)
    if explicit:
        windows = [
            (int(value.start_minute), int(value.end_minute))
            for value in explicit
        ]
    else:
        start = int(getattr(resource, "available_from_minute", 0) or 0)
        raw_end = getattr(resource, "available_until_minute", None)
        end = horizon if raw_end is None else int(raw_end)
        windows = [(start, end)]
    windows = sorted(windows)
    if not windows:
        raise PreparationRepairError(
            "resource_has_no_availability",
            "Revised resource contains no availability windows",
            resource_id=resource.resource_id,
        )
    previous_end = -1
    for start, end in windows:
        if start < 0 or end <= start or end > horizon:
            raise PreparationRepairError(
                "resource_window_invalid",
                "Revised resource window is outside the scheduling horizon",
                resource_id=resource.resource_id,
                start_minute=start,
                end_minute=end,
                horizon_minutes=horizon,
            )
        if start < previous_end:
            raise PreparationRepairError(
                "resource_windows_overlap",
                "Revised resource availability windows overlap",
                resource_id=resource.resource_id,
            )
        previous_end = end
    return windows


def _resource_maps(
    request: PreparationScheduleRequest,
) -> tuple[Dict[str, PreparationResource], Dict[str, List[Tuple[int, int]]]]:
    resources: Dict[str, PreparationResource] = {}
    windows: Dict[str, List[Tuple[int, int]]] = {}
    for resource in request.resources:
        if resource.resource_id in resources:
            raise PreparationRepairError(
                "duplicate_resource_id",
                "Revised request contains duplicate resource IDs",
                resource_id=resource.resource_id,
            )
        resources[resource.resource_id] = resource
        windows[resource.resource_id] = _resource_windows(
            resource,
            request.horizon_minutes,
        )
    return resources, windows


def _topological_order(tasks: Mapping[str, PreparationTask]) -> List[str]:
    indegree = {task_id: 0 for task_id in tasks}
    children: Dict[str, List[str]] = defaultdict(list)
    unknown: Dict[str, List[str]] = {}
    for task_id, task in tasks.items():
        missing = sorted(set(task.dependencies) - set(tasks))
        if missing:
            unknown[task_id] = missing
            continue
        for dependency in sorted(task.dependencies):
            indegree[task_id] += 1
            children[dependency].append(task_id)
    if unknown:
        raise PreparationRepairError(
            "unknown_dependencies",
            "Revised tasks reference unknown dependencies",
            tasks=unknown,
        )
    queue = [task_id for task_id, value in indegree.items() if value == 0]
    queue.sort()
    order: List[str] = []
    while queue:
        task_id = queue.pop(0)
        order.append(task_id)
        for child in sorted(children.get(task_id, [])):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
                queue.sort()
    if len(order) != len(tasks):
        cycle = sorted(task_id for task_id, value in indegree.items() if value > 0)
        raise PreparationRepairError(
            "dependency_cycle",
            "Revised preparation task graph contains a cycle",
            task_ids=cycle,
        )
    return order


def _candidate_bounds(
    task: PreparationTask,
    request: PreparationScheduleRequest,
    placements: Mapping[str, _Placement],
) -> tuple[int, int]:
    earliest = int(task.earliest_start_minute)
    if task.dependencies:
        earliest = max(
            earliest,
            max(placements[value].finish for value in task.dependencies),
        )
    latest = request.horizon_minutes - task.duration_minutes
    if task.latest_finish_minute is not None:
        latest = min(latest, int(task.latest_finish_minute) - task.duration_minutes)
    return earliest, latest


def _aligned_starts(
    earliest: int,
    latest: int,
    granularity: int,
) -> List[int]:
    if latest < earliest:
        return []
    first = int(math.ceil(earliest / granularity) * granularity)
    return list(range(first, latest + 1, granularity))


def _contained(
    start: int,
    finish: int,
    windows: Sequence[Tuple[int, int]],
) -> bool:
    return any(window_start <= start and finish <= window_end for window_start, window_end in windows)


def _capacity_feasible(
    *,
    resource_id: str,
    demand: int,
    start: int,
    finish: int,
    capacity: int,
    placements: Mapping[str, _Placement],
) -> bool:
    if demand > capacity:
        return False
    events: List[Tuple[int, int]] = [(start, demand), (finish, -demand)]
    for placement in placements.values():
        other = int(placement.task.resource_demands.get(resource_id, 0))
        if other <= 0:
            continue
        overlap_start = max(start, placement.start)
        overlap_finish = min(finish, placement.finish)
        if overlap_start < overlap_finish:
            events.append((placement.start, other))
            events.append((placement.finish, -other))
    usage = 0
    # Releases are processed before allocations at the same minute.
    for _, delta in sorted(events, key=lambda value: (value[0], value[1])):
        usage += delta
        if usage > capacity:
            return False
    return True


def _placement_issue(
    task: PreparationTask,
    start: int,
    request: PreparationScheduleRequest,
    resources: Mapping[str, PreparationResource],
    windows: Mapping[str, Sequence[Tuple[int, int]]],
    placements: Mapping[str, _Placement],
) -> tuple[str, dict] | None:
    finish = start + task.duration_minutes
    if start < task.earliest_start_minute:
        return "earliest_start", {"earliest_start_minute": task.earliest_start_minute}
    if finish > request.horizon_minutes:
        return "horizon", {"horizon_minutes": request.horizon_minutes}
    if task.latest_finish_minute is not None and finish > task.latest_finish_minute:
        return "deadline", {"latest_finish_minute": task.latest_finish_minute}
    blocked = [
        dependency
        for dependency in task.dependencies
        if dependency not in placements or placements[dependency].finish > start
    ]
    if blocked:
        return "dependency", {"blocked_by": sorted(blocked)}
    missing = sorted(set(task.resource_demands) - set(resources))
    if missing:
        return "missing_resource", {"missing_resources": missing}
    for resource_id, demand in sorted(task.resource_demands.items()):
        resource = resources[resource_id]
        if not _contained(start, finish, windows[resource_id]):
            return "availability", {"resource_id": resource_id}
        if not _capacity_feasible(
            resource_id=resource_id,
            demand=int(demand),
            start=start,
            finish=finish,
            capacity=int(resource.capacity),
            placements=placements,
        ):
            return "capacity", {
                "resource_id": resource_id,
                "required": int(demand),
                "capacity": int(resource.capacity),
            }
    return None


def _candidate_starts(
    *,
    task: PreparationTask,
    request: PreparationScheduleRequest,
    placements: Mapping[str, _Placement],
    previous_start: int | None,
    limit: int | None = None,
) -> List[int]:
    earliest, latest = _candidate_bounds(task, request, placements)
    starts = _aligned_starts(earliest, latest, request.granularity_minutes)
    if previous_start is None:
        ordered = starts
    else:
        ordered = sorted(
            starts,
            key=lambda value: (
                0 if value == previous_start else 1,
                abs(value - previous_start),
                value,
            ),
        )
    if limit is not None and len(ordered) > limit:
        return ordered[:limit]
    return ordered


def _unscheduled(
    task: PreparationTask,
    *,
    reason_code: str,
    message: str,
    details: Mapping[str, object] | None = None,
) -> UnscheduledPreparationTask:
    details = dict(details or {})
    missing = details.pop("missing_resources", [])
    blocked = details.pop("blocked_by", [])
    capacity: Dict[str, Dict[str, int]] = {}
    if reason_code == "capacity" and "resource_id" in details:
        resource_id = str(details["resource_id"])
        capacity[resource_id] = {
            "required": int(details.get("required", 0)),
            "capacity": int(details.get("capacity", 0)),
        }
    metadata = dict(task.metadata or {})
    metadata["repair_reason_details"] = details
    return UnscheduledPreparationTask(
        task_id=task.task_id,
        reason_code=reason_code,
        message=message,
        missing_resources=list(missing),
        blocked_by=list(blocked),
        capacity_violations=capacity,
        metadata=metadata,
    )


def _last_issue_for_task(
    task: PreparationTask,
    request: PreparationScheduleRequest,
    resources: Mapping[str, PreparationResource],
    windows: Mapping[str, Sequence[Tuple[int, int]]],
    placements: Mapping[str, _Placement],
) -> UnscheduledPreparationTask:
    missing_dependencies = sorted(
        dependency for dependency in task.dependencies if dependency not in placements
    )
    if missing_dependencies:
        return _unscheduled(
            task,
            reason_code="blocked_dependency",
            message="A required dependency could not be scheduled",
            details={"blocked_by": missing_dependencies},
        )
    missing_resources = sorted(set(task.resource_demands) - set(resources))
    if missing_resources:
        return _unscheduled(
            task,
            reason_code="missing_resource",
            message="One or more required resources are absent from the revised calendar",
            details={"missing_resources": missing_resources},
        )
    earliest, latest = _candidate_bounds(task, request, placements)
    starts = _aligned_starts(earliest, latest, request.granularity_minutes)
    if not starts:
        return _unscheduled(
            task,
            reason_code="deadline_infeasible",
            message="No start minute can satisfy the revised horizon and deadline",
            details={"earliest_start_minute": earliest, "latest_start_minute": latest},
        )
    saw_window = False
    saw_capacity = False
    capacity_detail: dict = {}
    for start in starts:
        finish = start + task.duration_minutes
        all_contained = True
        for resource_id in task.resource_demands:
            if resource_id not in windows or not _contained(start, finish, windows[resource_id]):
                all_contained = False
                break
        if not all_contained:
            continue
        saw_window = True
        issue = _placement_issue(task, start, request, resources, windows, placements)
        if issue and issue[0] == "capacity":
            saw_capacity = True
            capacity_detail = issue[1]
    if not saw_window:
        return _unscheduled(
            task,
            reason_code="availability_window_infeasible",
            message="The task cannot fit inside one continuous revised availability window",
        )
    if saw_capacity:
        return _unscheduled(
            task,
            reason_code="capacity_infeasible",
            message="The revised resource capacity cannot accommodate the task",
            details=capacity_detail,
        )
    return _unscheduled(
        task,
        reason_code="placement_infeasible",
        message="No deterministic feasible placement was found under revised constraints",
    )


def _validate_previous(
    request: PreparationScheduleRepairRequest,
) -> tuple[Dict[str, PreparationTask], Dict[str, ScheduledPreparationTask]]:
    previous_tasks = _task_map(request.previous_request.tasks, label="previous request")
    previous_scheduled = _scheduled_map(request.previous_response, label="previous response")
    if set(previous_tasks) != set(previous_scheduled):
        raise PreparationRepairError(
            "previous_schedule_task_set_mismatch",
            "Previous deterministic request and response task IDs differ",
            request_only=sorted(set(previous_tasks) - set(previous_scheduled)),
            response_only=sorted(set(previous_scheduled) - set(previous_tasks)),
        )
    for task_id, scheduled in previous_scheduled.items():
        source = previous_tasks[task_id]
        if (
            scheduled.duration_minutes != source.duration_minutes
            or scheduled.finish_minute - scheduled.start_minute != source.duration_minutes
            or dict(scheduled.resource_demands) != dict(source.resource_demands)
            or sorted(scheduled.dependencies) != sorted(source.dependencies)
        ):
            raise PreparationRepairError(
                "previous_schedule_snapshot_mismatch",
                "Previous deterministic response differs from its request",
                task_id=task_id,
            )
    return previous_tasks, previous_scheduled


def _pin_immutable(
    *,
    request: PreparationScheduleRepairRequest,
    previous_tasks: Mapping[str, PreparationTask],
    previous_scheduled: Mapping[str, ScheduledPreparationTask],
    revised_tasks: Mapping[str, PreparationTask],
    resources: Mapping[str, PreparationResource],
    windows: Mapping[str, Sequence[Tuple[int, int]]],
) -> Dict[str, _Placement]:
    immutable = set(request.immutable_task_ids)
    missing = sorted(immutable - set(revised_tasks))
    if missing:
        raise PreparationRepairError(
            "immutable_task_removed",
            "Immutable completed tasks cannot be removed from a repair request",
            task_ids=missing,
        )
    absent_previous = sorted(immutable - set(previous_scheduled))
    if absent_previous:
        raise PreparationRepairError(
            "immutable_task_not_in_previous_schedule",
            "Immutable tasks must exist in the previous deterministic schedule",
            task_ids=absent_previous,
        )
    changed = sorted(
        task_id
        for task_id in immutable
        if _operational_signature(previous_tasks[task_id])
        != _operational_signature(revised_tasks[task_id])
    )
    if changed:
        raise PreparationRepairError(
            "immutable_task_changed",
            "Immutable completed tasks cannot change duration, resources, or dependencies",
            task_ids=changed,
        )
    dependency_escape = {
        task_id: sorted(set(revised_tasks[task_id].dependencies) - immutable)
        for task_id in immutable
        if set(revised_tasks[task_id].dependencies) - immutable
    }
    if dependency_escape:
        raise PreparationRepairError(
            "immutable_dependency_not_pinned",
            "Every dependency of an immutable task must also be immutable",
            tasks=dependency_escape,
        )

    placements: Dict[str, _Placement] = {}
    for task_id in sorted(
        immutable,
        key=lambda value: (
            previous_scheduled[value].start_minute,
            previous_scheduled[value].finish_minute,
            value,
        ),
    ):
        task = revised_tasks[task_id]
        scheduled = previous_scheduled[task_id]
        issue = _placement_issue(
            task,
            scheduled.start_minute,
            request.revised_request,
            resources,
            windows,
            placements,
        )
        if issue:
            raise PreparationRepairError(
                "immutable_task_infeasible",
                "An immutable completed task is infeasible under revised constraints",
                task_id=task_id,
                previous_start_minute=scheduled.start_minute,
                reason_code=issue[0],
                details=issue[1],
            )
        placements[task_id] = _Placement(
            task=task,
            start=scheduled.start_minute,
            finish=scheduled.finish_minute,
        )
    return placements


def _greedy_repair(
    *,
    request: PreparationScheduleRepairRequest,
    previous_scheduled: Mapping[str, ScheduledPreparationTask],
    revised_tasks: Mapping[str, PreparationTask],
    order: Sequence[str],
    resources: Mapping[str, PreparationResource],
    windows: Mapping[str, Sequence[Tuple[int, int]]],
    initial: Mapping[str, _Placement],
    counters: _SearchCounters,
) -> tuple[Dict[str, _Placement], List[UnscheduledPreparationTask]]:
    placements = dict(initial)
    unscheduled: List[UnscheduledPreparationTask] = []
    immutable = set(request.immutable_task_ids)
    for task_id in order:
        if task_id in immutable:
            continue
        task = revised_tasks[task_id]
        if any(dependency not in placements for dependency in task.dependencies):
            unscheduled.append(
                _last_issue_for_task(
                    task,
                    request.revised_request,
                    resources,
                    windows,
                    placements,
                )
            )
            continue
        previous = previous_scheduled.get(task_id)
        if previous is not None:
            counters.preserved_attempts += 1
        selected: int | None = None
        for start in _candidate_starts(
            task=task,
            request=request.revised_request,
            placements=placements,
            previous_start=previous.start_minute if previous else None,
        ):
            counters.candidates += 1
            if _placement_issue(
                task,
                start,
                request.revised_request,
                resources,
                windows,
                placements,
            ) is None:
                selected = start
                break
        if selected is None:
            unscheduled.append(
                _last_issue_for_task(
                    task,
                    request.revised_request,
                    resources,
                    windows,
                    placements,
                )
            )
            continue
        placements[task_id] = _Placement(
            task=task,
            start=selected,
            finish=selected + task.duration_minutes,
        )
    return placements, unscheduled


def _classification(
    *,
    previous_tasks: Mapping[str, PreparationTask],
    previous_scheduled: Mapping[str, ScheduledPreparationTask],
    revised_tasks: Mapping[str, PreparationTask],
    placements: Mapping[str, _Placement],
    unscheduled_ids: Iterable[str],
) -> tuple[List[str], List[PreparationTaskMovement], List[str], List[str]]:
    unscheduled = set(unscheduled_ids)
    preserved: List[str] = []
    moved: List[PreparationTaskMovement] = []
    added: List[str] = []
    for task_id in sorted(revised_tasks):
        if task_id in unscheduled or task_id not in placements:
            continue
        placement = placements[task_id]
        if task_id not in previous_scheduled:
            added.append(task_id)
            continue
        previous = previous_scheduled[task_id]
        unchanged = (
            _operational_signature(previous_tasks[task_id])
            == _operational_signature(revised_tasks[task_id])
        )
        if unchanged and placement.start == previous.start_minute:
            preserved.append(task_id)
        else:
            moved.append(
                PreparationTaskMovement(
                    task_id=task_id,
                    previous_start_minute=previous.start_minute,
                    repaired_start_minute=placement.start,
                    displacement_minutes=placement.start - previous.start_minute,
                )
            )
    removed = sorted(set(previous_tasks) - set(revised_tasks))
    return preserved, moved, added, removed


def _objective_tuple(
    *,
    request: PreparationScheduleRepairRequest,
    previous_tasks: Mapping[str, PreparationTask],
    previous_scheduled: Mapping[str, ScheduledPreparationTask],
    revised_tasks: Mapping[str, PreparationTask],
    placements: Mapping[str, _Placement],
    unscheduled_ids: Sequence[str],
) -> tuple:
    preserved, moved, added, removed = _classification(
        previous_tasks=previous_tasks,
        previous_scheduled=previous_scheduled,
        revised_tasks=revised_tasks,
        placements=placements,
        unscheduled_ids=unscheduled_ids,
    )
    changed_count = len(moved) + len(added) + len(removed) + len(unscheduled_ids)
    displacement = sum(abs(value.displacement_minutes) for value in moved)
    makespan = max((value.finish for value in placements.values()), default=0)
    starts = tuple((task_id, placements[task_id].start) for task_id in sorted(placements))
    return (len(unscheduled_ids), changed_count, displacement, makespan, starts)


def _exact_repair(
    *,
    request: PreparationScheduleRepairRequest,
    previous_tasks: Mapping[str, PreparationTask],
    previous_scheduled: Mapping[str, ScheduledPreparationTask],
    revised_tasks: Mapping[str, PreparationTask],
    order: Sequence[str],
    resources: Mapping[str, PreparationResource],
    windows: Mapping[str, Sequence[Tuple[int, int]]],
    initial: Mapping[str, _Placement],
    counters: _SearchCounters,
) -> tuple[Dict[str, _Placement], List[UnscheduledPreparationTask]]:
    mutable_order = [value for value in order if value not in set(request.immutable_task_ids)]
    if len(mutable_order) > request.exact_task_limit:
        counters.truncated = True
        return _greedy_repair(
            request=request,
            previous_scheduled=previous_scheduled,
            revised_tasks=revised_tasks,
            order=order,
            resources=resources,
            windows=windows,
            initial=initial,
            counters=counters,
        )

    best: tuple | None = None
    best_placements: Dict[str, _Placement] | None = None
    best_unscheduled: List[str] | None = None

    def search(index: int, placements: Dict[str, _Placement], unscheduled_ids: List[str]) -> None:
        nonlocal best, best_placements, best_unscheduled
        counters.explored += 1
        if best is not None and len(unscheduled_ids) > best[0]:
            counters.pruned += 1
            return
        if index >= len(mutable_order):
            objective = _objective_tuple(
                request=request,
                previous_tasks=previous_tasks,
                previous_scheduled=previous_scheduled,
                revised_tasks=revised_tasks,
                placements=placements,
                unscheduled_ids=unscheduled_ids,
            )
            if best is None or objective < best:
                best = objective
                best_placements = dict(placements)
                best_unscheduled = list(unscheduled_ids)
            return

        task_id = mutable_order[index]
        task = revised_tasks[task_id]
        if any(dependency not in placements for dependency in task.dependencies):
            search(index + 1, placements, [*unscheduled_ids, task_id])
            return
        previous = previous_scheduled.get(task_id)
        starts = _candidate_starts(
            task=task,
            request=request.revised_request,
            placements=placements,
            previous_start=previous.start_minute if previous else None,
            limit=request.exact_candidate_limit_per_task,
        )
        feasible_count = 0
        for start in starts:
            counters.candidates += 1
            if _placement_issue(
                task,
                start,
                request.revised_request,
                resources,
                windows,
                placements,
            ) is not None:
                continue
            feasible_count += 1
            placements[task_id] = _Placement(
                task=task,
                start=start,
                finish=start + task.duration_minutes,
            )
            search(index + 1, placements, unscheduled_ids)
            placements.pop(task_id, None)
        if request.allow_partial or feasible_count == 0:
            search(index + 1, placements, [*unscheduled_ids, task_id])

    search(0, dict(initial), [])
    if best_placements is None or best_unscheduled is None:
        raise PreparationRepairError(
            "repair_search_failed",
            "Bounded exact repair did not produce a candidate",
        )
    unscheduled = [
        _last_issue_for_task(
            revised_tasks[task_id],
            request.revised_request,
            resources,
            windows,
            best_placements,
        )
        for task_id in best_unscheduled
    ]
    return best_placements, unscheduled


def _scheduled_task(placement: _Placement) -> ScheduledPreparationTask:
    task = placement.task
    metadata = dict(task.metadata or {})
    metadata["repair_previous_or_revised_task_id"] = task.task_id
    return ScheduledPreparationTask(
        task_id=task.task_id,
        start_minute=placement.start,
        finish_minute=placement.finish,
        duration_minutes=task.duration_minutes,
        priority=task.priority,
        resource_demands=dict(sorted(task.resource_demands.items())),
        dependencies=list(task.dependencies),
        metadata=metadata,
    )


def _utilization(
    *,
    request: PreparationScheduleRequest,
    resources: Mapping[str, PreparationResource],
    windows: Mapping[str, Sequence[Tuple[int, int]]],
    placements: Mapping[str, _Placement],
) -> tuple[Dict[str, float], Dict[str, int]]:
    utilization: Dict[str, float] = {}
    peaks: Dict[str, int] = {}
    for resource_id, resource in sorted(resources.items()):
        used = sum(
            placement.task.resource_demands.get(resource_id, 0)
            * (placement.finish - placement.start)
            for placement in placements.values()
        )
        available = resource.capacity * sum(end - start for start, end in windows[resource_id])
        utilization[resource_id] = round(used / available, 8) if available else 0.0
        events: List[Tuple[int, int]] = []
        for placement in placements.values():
            demand = int(placement.task.resource_demands.get(resource_id, 0))
            if demand:
                events.append((placement.start, demand))
                events.append((placement.finish, -demand))
        usage = 0
        peak = 0
        for _, delta in sorted(events, key=lambda value: (value[0], value[1])):
            usage += delta
            peak = max(peak, usage)
        peaks[resource_id] = peak
    return utilization, peaks


def repair_preparation_schedule(
    request: PreparationScheduleRepairRequest,
) -> PreparationScheduleRepairResult:
    """Return a deterministic non-persisted minimal-change repair candidate."""

    previous_tasks, previous_scheduled = _validate_previous(request)
    revised_tasks = _task_map(request.revised_request.tasks, label="revised request")
    order = _topological_order(revised_tasks)
    resources, windows = _resource_maps(request.revised_request)
    immutable_placements = _pin_immutable(
        request=request,
        previous_tasks=previous_tasks,
        previous_scheduled=previous_scheduled,
        revised_tasks=revised_tasks,
        resources=resources,
        windows=windows,
    )
    counters = _SearchCounters()
    if request.strategy == PreparationRepairStrategy.BOUNDED_EXACT_MIN_CHANGE:
        placements, unscheduled = _exact_repair(
            request=request,
            previous_tasks=previous_tasks,
            previous_scheduled=previous_scheduled,
            revised_tasks=revised_tasks,
            order=order,
            resources=resources,
            windows=windows,
            initial=immutable_placements,
            counters=counters,
        )
    else:
        placements, unscheduled = _greedy_repair(
            request=request,
            previous_scheduled=previous_scheduled,
            revised_tasks=revised_tasks,
            order=order,
            resources=resources,
            windows=windows,
            initial=immutable_placements,
            counters=counters,
        )

    unscheduled_ids = sorted(value.task_id for value in unscheduled)
    if unscheduled_ids and not request.allow_partial:
        raise PreparationRepairError(
            "repair_infeasible",
            "No complete deterministic repair exists under the selected strategy and revised constraints",
            unscheduled_task_ids=unscheduled_ids,
            strategy=request.strategy.value,
        )
    preserved, moved, added, removed = _classification(
        previous_tasks=previous_tasks,
        previous_scheduled=previous_scheduled,
        revised_tasks=revised_tasks,
        placements=placements,
        unscheduled_ids=unscheduled_ids,
    )
    scheduled = sorted(
        (_scheduled_task(value) for value in placements.values()),
        key=lambda value: (value.start_minute, value.finish_minute, value.task_id),
    )
    utilization, peaks = _utilization(
        request=request.revised_request,
        resources=resources,
        windows=windows,
        placements=placements,
    )
    makespan = max((value.finish_minute for value in scheduled), default=0)
    changed_count = len(moved) + len(added) + len(removed) + len(unscheduled_ids)
    displacement = sum(abs(value.displacement_minutes) for value in moved)
    weighted = (
        len(unscheduled_ids) * request.weights.unscheduled_task
        + changed_count * request.weights.changed_task
        + displacement * request.weights.displacement_minute
        + makespan * request.weights.makespan_minute
    )
    diagnostics_payload = {
        "repair_strategy": request.strategy.value,
        "immutable_task_ids": request.immutable_task_ids,
        "preserved_task_ids": preserved,
        "moved_task_ids": [value.task_id for value in moved],
        "added_task_ids": added,
        "removed_task_ids": removed,
        "unscheduled_task_ids": unscheduled_ids,
        "objective": {
            "unscheduled_task_count": len(unscheduled_ids),
            "changed_task_count": changed_count,
            "total_displacement_minutes": displacement,
            "makespan_minutes": makespan,
            "weighted_value": weighted,
        },
        "search": {
            "explored_states": counters.explored,
            "pruned_states": counters.pruned,
            "candidate_placements_considered": counters.candidates,
            "preserved_attempt_count": counters.preserved_attempts,
            "exact_search_truncated": counters.truncated,
        },
    }
    response = PreparationScheduleResponse(
        method="deterministic_minimal_change_preparation_repair_v1",
        deterministic=True,
        horizon_minutes=request.revised_request.horizon_minutes,
        granularity_minutes=request.revised_request.granularity_minutes,
        scheduled=scheduled,
        unscheduled=unscheduled,
        resource_utilization=utilization,
        resource_peak_usage=peaks,
        makespan_minutes=makespan,
        diagnostics=diagnostics_payload,
    )
    previous_hash = _canonical_hash(request.previous_response.model_dump(mode="json"))
    request_hash = _canonical_hash(request.revised_request.model_dump(mode="json"))
    response_hash = _canonical_hash(response.model_dump(mode="json"))
    warnings = [
        "Repair output is non-persisted and never mutates the previous schedule",
        "Human review and explicit acceptance are required before any new schedule is persisted",
        "Completed or otherwise immutable work is pinned exactly and causes fail-closed rejection when infeasible",
    ]
    if counters.truncated:
        warnings.append(
            "Bounded exact search exceeded the configured task limit and used the deterministic greedy repair"
        )
    if unscheduled_ids:
        warnings.append(
            "Partial repair retains explicit unscheduled work; it cannot be treated as an executable complete schedule"
        )
    return PreparationScheduleRepairResult(
        response=response,
        complete=not unscheduled_ids,
        immutable_task_ids=list(request.immutable_task_ids),
        preserved_task_ids=preserved,
        moved_tasks=moved,
        added_task_ids=added,
        removed_task_ids=removed,
        unscheduled_task_ids=unscheduled_ids,
        objective=PreparationRepairObjective(
            unscheduled_task_count=len(unscheduled_ids),
            changed_task_count=changed_count,
            total_displacement_minutes=displacement,
            makespan_minutes=makespan,
            weighted_value=weighted,
        ),
        diagnostics=PreparationRepairDiagnostics(
            strategy=request.strategy,
            explored_states=counters.explored,
            pruned_states=counters.pruned,
            candidate_placements_considered=counters.candidates,
            preserved_attempt_count=counters.preserved_attempts,
            exact_search_truncated=counters.truncated,
            tie_break_rule=(
                "lexicographic unscheduled count, changed task count, total absolute displacement, "
                "makespan, then task-id/start-minute vector"
            ),
            limitations=[
                "No meal-selection repair or pantry mutation is performed",
                "No execution event is inferred, fabricated, or rewritten",
                "Exact search is bounded and intended only as a small-instance comparator",
            ],
        ),
        warnings=warnings,
        previous_schedule_hash=previous_hash,
        revised_request_hash=request_hash,
        repaired_response_hash=response_hash,
    )


__all__ = ["PreparationRepairError", "repair_preparation_schedule"]
