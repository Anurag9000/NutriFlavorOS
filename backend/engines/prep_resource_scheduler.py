"""Deterministic dependency- and capacity-aware preparation scheduling.

This is an interval-capacity scheduler, not a duration estimator. Every task
must carry explicit duration, dependencies, and resource demands. The algorithm
processes a validated DAG, schedules urgent ready work at the earliest feasible
aligned start, and reports every rejection with machine-readable diagnostics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, Iterable, List, Tuple

from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleRequest,
    PreparationScheduleResponse,
    PreparationTask,
    ScheduledPreparationTask,
    UnscheduledPreparationTask,
)


@dataclass(frozen=True)
class _Reservation:
    start: int
    finish: int
    demand: int
    task_id: str


def _align_up(value: int, granularity: int) -> int:
    return ((value + granularity - 1) // granularity) * granularity


def resource_availability_windows(
    resource: PreparationResource,
    horizon: int,
) -> List[Tuple[int, int]]:
    """Return canonical continuous windows for one resource.

    Explicit reviewed windows are kept distinct, including adjacent windows.
    Legacy single-window fields are translated without mutating the request.
    """

    if resource.availability_windows:
        return [
            (window.start_minute, window.end_minute)
            for window in resource.availability_windows
        ]
    start = resource.available_from_minute
    end = min(horizon, resource.available_until_minute or horizon)
    return [(start, end)] if start < end else []


def _is_contained_in_window(
    resource: PreparationResource,
    *,
    start: int,
    finish: int,
    horizon: int,
) -> bool:
    return any(
        start >= window_start and finish <= window_end
        for window_start, window_end in resource_availability_windows(
            resource,
            horizon,
        )
    )


def _peak_usage(intervals: Iterable[_Reservation]) -> int:
    events: List[Tuple[int, int]] = []
    for interval in intervals:
        events.append((interval.start, interval.demand))
        events.append((interval.finish, -interval.demand))
    usage = 0
    peak = 0
    # Releases at a timestamp are processed before acquisitions at that same
    # timestamp, so back-to-back tasks do not falsely overlap.
    for _, delta in sorted(
        events,
        key=lambda event: (event[0], 0 if event[1] < 0 else 1),
    ):
        usage += delta
        peak = max(peak, usage)
    return peak


def _fits_capacity(
    reservations: List[_Reservation],
    *,
    start: int,
    finish: int,
    demand: int,
    capacity: int,
) -> bool:
    relevant = [
        reservation
        for reservation in reservations
        if reservation.start < finish and start < reservation.finish
    ]
    relevant.append(_Reservation(start, finish, demand, "__candidate__"))
    return _peak_usage(relevant) <= capacity


def _task_order(task: PreparationTask, horizon: int) -> tuple[int, int, int, str]:
    deadline = min(task.latest_finish_minute or horizon, horizon)
    return (deadline, -task.priority, task.earliest_start_minute, task.task_id)


def _critical_path_lower_bound(tasks: Dict[str, PreparationTask]) -> int:
    memo: Dict[str, int] = {}

    def finish(task_id: str) -> int:
        if task_id in memo:
            return memo[task_id]
        task = tasks[task_id]
        dependency_finish = max(
            (finish(value) for value in task.dependencies),
            default=0,
        )
        memo[task_id] = dependency_finish + task.duration_minutes
        return memo[task_id]

    return max((finish(task_id) for task_id in tasks), default=0)


def build_preparation_schedule(
    request: PreparationScheduleRequest,
) -> PreparationScheduleResponse:
    resources = {resource.resource_id: resource for resource in request.resources}
    tasks = {task.task_id: task for task in request.tasks}
    reservations: DefaultDict[str, List[_Reservation]] = defaultdict(list)
    scheduled: List[ScheduledPreparationTask] = []
    unscheduled: List[UnscheduledPreparationTask] = []
    scheduled_by_id: Dict[str, ScheduledPreparationTask] = {}
    unscheduled_by_id: Dict[str, UnscheduledPreparationTask] = {}
    candidate_starts_inspected = 0
    pending = set(tasks)

    while pending:
        ready = [
            tasks[task_id]
            for task_id in pending
            if all(
                dependency not in pending
                for dependency in tasks[task_id].dependencies
            )
        ]
        if not ready:
            raise RuntimeError(
                "Validated preparation dependency DAG became unschedulable"
            )

        for task in sorted(
            ready,
            key=lambda value: _task_order(value, request.horizon_minutes),
        ):
            pending.remove(task.task_id)
            blocked_by = sorted(
                dependency
                for dependency in task.dependencies
                if dependency in unscheduled_by_id
            )
            if blocked_by:
                value = UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code="blocked_by_dependency",
                    message="One or more prerequisite tasks were not scheduled",
                    blocked_by=blocked_by,
                    metadata=task.metadata,
                )
                unscheduled.append(value)
                unscheduled_by_id[task.task_id] = value
                continue

            missing = sorted(set(task.resource_demands) - set(resources))
            if missing:
                value = UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code="missing_resource",
                    message=(
                        "One or more declared resources are not present in the "
                        "capacity request"
                    ),
                    missing_resources=missing,
                    metadata=task.metadata,
                )
                unscheduled.append(value)
                unscheduled_by_id[task.task_id] = value
                continue

            capacity_violations = {
                resource_id: {
                    "requested": demand,
                    "capacity": resources[resource_id].capacity,
                }
                for resource_id, demand in sorted(task.resource_demands.items())
                if demand > resources[resource_id].capacity
            }
            if capacity_violations:
                value = UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code="capacity_exceeded",
                    message="A task demand exceeds declared resource capacity",
                    capacity_violations=capacity_violations,
                    metadata=task.metadata,
                )
                unscheduled.append(value)
                unscheduled_by_id[task.task_id] = value
                continue

            dependency_finish = max(
                (
                    scheduled_by_id[dependency].finish_minute
                    for dependency in task.dependencies
                ),
                default=0,
            )
            latest_finish = min(
                task.latest_finish_minute or request.horizon_minutes,
                request.horizon_minutes,
            )
            earliest = _align_up(
                max(task.earliest_start_minute, dependency_finish),
                request.granularity_minutes,
            )
            latest_start = latest_finish - task.duration_minutes
            if earliest > latest_start:
                reason = (
                    "dependency_window_too_short"
                    if dependency_finish > task.earliest_start_minute
                    else "window_too_short"
                )
                value = UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code=reason,
                    message=(
                        "The task cannot fit after its dependencies and before "
                        "its deadline"
                        if reason == "dependency_window_too_short"
                        else "The declared duration does not fit inside the task window"
                    ),
                    blocked_by=(
                        list(task.dependencies)
                        if reason == "dependency_window_too_short"
                        else []
                    ),
                    metadata=task.metadata,
                )
                unscheduled.append(value)
                unscheduled_by_id[task.task_id] = value
                continue

            chosen_start = None
            window_feasible_seen = not task.resource_demands
            for start in range(
                earliest,
                latest_start + 1,
                request.granularity_minutes,
            ):
                candidate_starts_inspected += 1
                finish = start + task.duration_minutes
                windows_fit = all(
                    _is_contained_in_window(
                        resources[resource_id],
                        start=start,
                        finish=finish,
                        horizon=request.horizon_minutes,
                    )
                    for resource_id in task.resource_demands
                )
                if not windows_fit:
                    continue
                window_feasible_seen = True
                capacities_fit = all(
                    _fits_capacity(
                        reservations[resource_id],
                        start=start,
                        finish=finish,
                        demand=demand,
                        capacity=resources[resource_id].capacity,
                    )
                    for resource_id, demand in task.resource_demands.items()
                )
                if capacities_fit:
                    chosen_start = start
                    break

            if chosen_start is None:
                reason_code = (
                    "no_feasible_resource_window"
                    if window_feasible_seen
                    else "resource_availability_infeasible"
                )
                value = UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code=reason_code,
                    message=(
                        "No aligned interval has sufficient remaining resource capacity"
                        if window_feasible_seen
                        else "The task cannot fit wholly inside one declared "
                        "availability window for every required resource"
                    ),
                    metadata=task.metadata,
                )
                unscheduled.append(value)
                unscheduled_by_id[task.task_id] = value
                continue

            finish = chosen_start + task.duration_minutes
            scheduled_task = ScheduledPreparationTask(
                task_id=task.task_id,
                start_minute=chosen_start,
                finish_minute=finish,
                duration_minutes=task.duration_minutes,
                priority=task.priority,
                resource_demands=dict(sorted(task.resource_demands.items())),
                dependencies=list(task.dependencies),
                metadata=task.metadata,
            )
            scheduled.append(scheduled_task)
            scheduled_by_id[task.task_id] = scheduled_task
            for resource_id, demand in task.resource_demands.items():
                reservations[resource_id].append(
                    _Reservation(chosen_start, finish, demand, task.task_id)
                )

    utilization: Dict[str, float] = {}
    peaks: Dict[str, int] = {}
    window_counts: Dict[str, int] = {}
    for resource_id, resource in sorted(resources.items()):
        windows = resource_availability_windows(
            resource,
            request.horizon_minutes,
        )
        available_minutes = sum(end - start for start, end in windows)
        denominator = available_minutes * resource.capacity
        used = sum(
            (reservation.finish - reservation.start) * reservation.demand
            for reservation in reservations[resource_id]
        )
        utilization[resource_id] = (
            round(used / denominator, 6) if denominator else 0.0
        )
        peaks[resource_id] = _peak_usage(reservations[resource_id])
        window_counts[resource_id] = len(windows)

    scheduled.sort(
        key=lambda task: (task.start_minute, task.finish_minute, task.task_id)
    )
    unscheduled.sort(key=lambda task: task.task_id)
    makespan = max((task.finish_minute for task in scheduled), default=0)
    return PreparationScheduleResponse(
        horizon_minutes=request.horizon_minutes,
        granularity_minutes=request.granularity_minutes,
        scheduled=scheduled,
        unscheduled=unscheduled,
        resource_utilization=utilization,
        resource_peak_usage=peaks,
        makespan_minutes=makespan,
        diagnostics={
            "task_count": len(request.tasks),
            "scheduled_count": len(scheduled),
            "unscheduled_count": len(unscheduled),
            "resource_count": len(request.resources),
            "resource_window_counts": window_counts,
            "dependency_edge_count": sum(
                len(task.dependencies) for task in request.tasks
            ),
            "critical_path_lower_bound_minutes": _critical_path_lower_bound(tasks),
            "candidate_starts_inspected": candidate_starts_inspected,
            "ordering": (
                "topological_ready_set_then_deadline_priority_"
                "earliest_start_task_id"
            ),
        },
    )
