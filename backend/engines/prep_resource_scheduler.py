"""Deterministic preparation-resource scheduling.

This is an interval-capacity scheduler, not a duration estimator. Every task
must carry explicit duration and resource demands. The algorithm schedules
higher-urgency work at the earliest feasible aligned start and reports every
rejection with machine-readable diagnostics.
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


def _resource_end(resource: PreparationResource, horizon: int) -> int:
    return min(horizon, resource.available_until_minute or horizon)


def _peak_usage(intervals: Iterable[_Reservation]) -> int:
    events: List[Tuple[int, int]] = []
    for interval in intervals:
        events.append((interval.start, interval.demand))
        events.append((interval.finish, -interval.demand))
    usage = 0
    peak = 0
    for _, delta in sorted(events, key=lambda event: (event[0], 0 if event[1] < 0 else 1)):
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
        _Reservation(
            start=max(start, reservation.start),
            finish=min(finish, reservation.finish),
            demand=reservation.demand,
            task_id=reservation.task_id,
        )
        for reservation in reservations
        if reservation.start < finish and reservation.finish > start
    ]
    relevant.append(_Reservation(start, finish, demand, "__candidate__"))
    return _peak_usage(relevant) <= capacity


def _task_order(task: PreparationTask, horizon: int) -> tuple[int, int, int, str]:
    deadline = min(task.latest_finish_minute or horizon, horizon)
    return (deadline, -task.priority, task.earliest_start_minute, task.task_id)


def build_preparation_schedule(
    request: PreparationScheduleRequest,
) -> PreparationScheduleResponse:
    resources = {resource.resource_id: resource for resource in request.resources}
    reservations: DefaultDict[str, List[_Reservation]] = defaultdict(list)
    scheduled: List[ScheduledPreparationTask] = []
    unscheduled: List[UnscheduledPreparationTask] = []
    candidate_starts_inspected = 0

    for task in sorted(request.tasks, key=lambda value: _task_order(value, request.horizon_minutes)):
        missing = sorted(set(task.resource_demands) - set(resources))
        if missing:
            unscheduled.append(
                UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code="missing_resource",
                    message="One or more declared resources are not present in the capacity request",
                    missing_resources=missing,
                    metadata=task.metadata,
                )
            )
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
            unscheduled.append(
                UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code="capacity_exceeded",
                    message="A task demand exceeds declared resource capacity",
                    capacity_violations=capacity_violations,
                    metadata=task.metadata,
                )
            )
            continue

        latest_finish = min(task.latest_finish_minute or request.horizon_minutes, request.horizon_minutes)
        earliest = _align_up(task.earliest_start_minute, request.granularity_minutes)
        latest_start = latest_finish - task.duration_minutes
        if earliest > latest_start:
            unscheduled.append(
                UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code="window_too_short",
                    message="The declared duration does not fit inside the task window",
                    metadata=task.metadata,
                )
            )
            continue

        chosen_start = None
        for start in range(earliest, latest_start + 1, request.granularity_minutes):
            candidate_starts_inspected += 1
            finish = start + task.duration_minutes
            feasible = True
            for resource_id, demand in task.resource_demands.items():
                resource = resources[resource_id]
                if (
                    start < resource.available_from_minute
                    or finish > _resource_end(resource, request.horizon_minutes)
                ):
                    feasible = False
                    break
                if not _fits_capacity(
                    reservations[resource_id],
                    start=start,
                    finish=finish,
                    demand=demand,
                    capacity=resource.capacity,
                ):
                    feasible = False
                    break
            if feasible:
                chosen_start = start
                break

        if chosen_start is None:
            unscheduled.append(
                UnscheduledPreparationTask(
                    task_id=task.task_id,
                    reason_code="no_feasible_resource_window",
                    message="No aligned interval satisfies all declared capacities and availability windows",
                    metadata=task.metadata,
                )
            )
            continue

        finish = chosen_start + task.duration_minutes
        scheduled_task = ScheduledPreparationTask(
            task_id=task.task_id,
            start_minute=chosen_start,
            finish_minute=finish,
            duration_minutes=task.duration_minutes,
            priority=task.priority,
            resource_demands=dict(sorted(task.resource_demands.items())),
            metadata=task.metadata,
        )
        scheduled.append(scheduled_task)
        for resource_id, demand in task.resource_demands.items():
            reservations[resource_id].append(
                _Reservation(chosen_start, finish, demand, task.task_id)
            )

    utilization: Dict[str, float] = {}
    peaks: Dict[str, int] = {}
    for resource_id, resource in sorted(resources.items()):
        available_minutes = max(
            0,
            _resource_end(resource, request.horizon_minutes)
            - resource.available_from_minute,
        )
        denominator = available_minutes * resource.capacity
        used = sum(
            (reservation.finish - reservation.start) * reservation.demand
            for reservation in reservations[resource_id]
        )
        utilization[resource_id] = round(used / denominator, 6) if denominator else 0.0
        peaks[resource_id] = _peak_usage(reservations[resource_id])

    scheduled.sort(key=lambda task: (task.start_minute, task.finish_minute, task.task_id))
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
            "candidate_starts_inspected": candidate_starts_inspected,
            "ordering": "deadline_then_priority_then_earliest_start_then_task_id",
        },
    )
