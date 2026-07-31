"""Exact branch-and-bound preparation scheduling for bounded fixtures.

This solver is an offline comparator for small deterministic problems. It uses
the same explicit task/resource contract as the product heuristic, searches all
aligned feasible starts under a node budget, and optimizes complete-schedule
makespan followed by total start time and a deterministic signature.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, Iterable, List, Sequence, Tuple

from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleRequest,
    PreparationScheduleResponse,
    PreparationTask,
    ScheduledPreparationTask,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule


class ExactPreparationInfeasible(ValueError):
    """Raised when no complete aligned schedule exists."""


class ExactPreparationSearchLimit(RuntimeError):
    """Raised when the configured exact-search budget is exhausted."""


@dataclass(frozen=True)
class _Interval:
    start: int
    finish: int
    demand: int
    task_id: str


@dataclass(frozen=True)
class ExactPreparationResult:
    schedule: PreparationScheduleResponse
    optimal_makespan_minutes: int
    total_start_minutes: int
    nodes_visited: int
    complete_schedules_evaluated: int
    search_exhausted: bool


@dataclass(frozen=True)
class PreparationScheduleComparison:
    heuristic: PreparationScheduleResponse
    exact: ExactPreparationResult
    heuristic_complete: bool
    exact_complete: bool
    makespan_gap_minutes: int | None
    makespan_ratio: float | None


def _align_up(value: int, granularity: int) -> int:
    return ((value + granularity - 1) // granularity) * granularity


def _resource_end(resource: PreparationResource, horizon: int) -> int:
    return min(horizon, resource.available_until_minute or horizon)


def _peak_usage(intervals: Iterable[_Interval]) -> int:
    events: List[Tuple[int, int]] = []
    for interval in intervals:
        events.append((interval.start, interval.demand))
        events.append((interval.finish, -interval.demand))
    usage = 0
    peak = 0
    for _, delta in sorted(
        events,
        key=lambda event: (event[0], 0 if event[1] < 0 else 1),
    ):
        usage += delta
        peak = max(peak, usage)
    return peak


def _fits(
    intervals: Sequence[_Interval],
    *,
    start: int,
    finish: int,
    demand: int,
    capacity: int,
) -> bool:
    relevant = [
        _Interval(
            max(start, value.start),
            min(finish, value.finish),
            value.demand,
            value.task_id,
        )
        for value in intervals
        if value.start < finish and value.finish > start
    ]
    relevant.append(_Interval(start, finish, demand, "__candidate__"))
    return _peak_usage(relevant) <= capacity


def _candidate_starts(
    task: PreparationTask,
    *,
    request: PreparationScheduleRequest,
    resources: Dict[str, PreparationResource],
    scheduled: Dict[str, ScheduledPreparationTask],
    reservations: Dict[str, List[_Interval]],
) -> List[int]:
    dependency_finish = max(
        (scheduled[value].finish_minute for value in task.dependencies),
        default=0,
    )
    earliest = _align_up(
        max(task.earliest_start_minute, dependency_finish),
        request.granularity_minutes,
    )
    latest_finish = min(
        task.latest_finish_minute or request.horizon_minutes,
        request.horizon_minutes,
    )
    latest_start = latest_finish - task.duration_minutes
    if earliest > latest_start:
        return []

    starts = []
    for start in range(
        earliest,
        latest_start + 1,
        request.granularity_minutes,
    ):
        finish = start + task.duration_minutes
        feasible = True
        for resource_id, demand in task.resource_demands.items():
            resource = resources[resource_id]
            if (
                start < resource.available_from_minute
                or finish > _resource_end(resource, request.horizon_minutes)
                or not _fits(
                    reservations.get(resource_id, []),
                    start=start,
                    finish=finish,
                    demand=demand,
                    capacity=resource.capacity,
                )
            ):
                feasible = False
                break
        if feasible:
            starts.append(start)
    return starts


def _validate_exact_request(
    request: PreparationScheduleRequest,
    *,
    maximum_tasks: int,
) -> Dict[str, PreparationResource]:
    if len(request.tasks) > maximum_tasks:
        raise ValueError(
            f"exact scheduler supports at most {maximum_tasks} tasks; received {len(request.tasks)}"
        )
    resources = {value.resource_id: value for value in request.resources}
    for task in request.tasks:
        missing = sorted(set(task.resource_demands) - set(resources))
        if missing:
            raise ExactPreparationInfeasible(
                f"task {task.task_id} references missing resources: {', '.join(missing)}"
            )
        excessive = [
            resource_id
            for resource_id, demand in task.resource_demands.items()
            if demand > resources[resource_id].capacity
        ]
        if excessive:
            raise ExactPreparationInfeasible(
                f"task {task.task_id} exceeds capacity for: {', '.join(sorted(excessive))}"
            )
    return resources


def exact_preparation_schedule(
    request: PreparationScheduleRequest,
    *,
    maximum_tasks: int = 10,
    maximum_nodes: int = 1_000_000,
) -> ExactPreparationResult:
    """Return an optimal complete aligned schedule for a bounded fixture."""

    if maximum_tasks < 1:
        raise ValueError("maximum_tasks must be at least 1")
    if maximum_nodes < 1:
        raise ValueError("maximum_nodes must be at least 1")
    resources = _validate_exact_request(request, maximum_tasks=maximum_tasks)
    tasks = {value.task_id: value for value in request.tasks}
    reservations: DefaultDict[str, List[_Interval]] = defaultdict(list)
    scheduled: Dict[str, ScheduledPreparationTask] = {}
    best: tuple[
        tuple[int, int, Tuple[Tuple[str, int], ...]],
        Dict[str, ScheduledPreparationTask],
    ] | None = None
    nodes_visited = 0
    complete_evaluated = 0

    def visit() -> None:
        nonlocal best, nodes_visited, complete_evaluated
        nodes_visited += 1
        if nodes_visited > maximum_nodes:
            raise ExactPreparationSearchLimit(
                f"exact preparation search exceeded {maximum_nodes} nodes"
            )
        if len(scheduled) == len(tasks):
            complete_evaluated += 1
            makespan = max(
                (value.finish_minute for value in scheduled.values()),
                default=0,
            )
            total_start = sum(value.start_minute for value in scheduled.values())
            signature = tuple(
                sorted(
                    (task_id, value.start_minute)
                    for task_id, value in scheduled.items()
                )
            )
            objective = (makespan, total_start, signature)
            if best is None or objective < best[0]:
                best = (objective, dict(scheduled))
            return

        current_makespan = max(
            (value.finish_minute for value in scheduled.values()),
            default=0,
        )
        if best is not None and current_makespan > best[0][0]:
            return

        ready = [
            task
            for task_id, task in tasks.items()
            if task_id not in scheduled
            and all(value in scheduled for value in task.dependencies)
        ]
        if not ready:
            raise RuntimeError("validated dependency DAG has no ready task")

        choices = []
        for task in ready:
            starts = _candidate_starts(
                task,
                request=request,
                resources=resources,
                scheduled=scheduled,
                reservations=reservations,
            )
            choices.append((len(starts), task.task_id, task, starts))
        _, _, task, starts = min(choices, key=lambda value: (value[0], value[1]))
        if not starts:
            return

        for start in starts:
            finish = start + task.duration_minutes
            if best is not None and max(current_makespan, finish) > best[0][0]:
                continue
            value = ScheduledPreparationTask(
                task_id=task.task_id,
                start_minute=start,
                finish_minute=finish,
                duration_minutes=task.duration_minutes,
                priority=task.priority,
                resource_demands=dict(sorted(task.resource_demands.items())),
                dependencies=list(task.dependencies),
                metadata=task.metadata,
            )
            scheduled[task.task_id] = value
            added = []
            for resource_id, demand in task.resource_demands.items():
                interval = _Interval(start, finish, demand, task.task_id)
                reservations[resource_id].append(interval)
                added.append((resource_id, interval))
            visit()
            for resource_id, interval in reversed(added):
                reservations[resource_id].remove(interval)
            del scheduled[task.task_id]

    visit()
    if best is None:
        raise ExactPreparationInfeasible(
            "no complete aligned preparation schedule satisfies all declared constraints"
        )

    objective, best_schedule = best
    scheduled_values = sorted(
        best_schedule.values(),
        key=lambda value: (
            value.start_minute,
            value.finish_minute,
            value.task_id,
        ),
    )
    utilization: Dict[str, float] = {}
    peaks: Dict[str, int] = {}
    for resource_id, resource in sorted(resources.items()):
        intervals = [
            _Interval(
                value.start_minute,
                value.finish_minute,
                value.resource_demands[resource_id],
                value.task_id,
            )
            for value in scheduled_values
            if resource_id in value.resource_demands
        ]
        available = max(
            0,
            _resource_end(resource, request.horizon_minutes)
            - resource.available_from_minute,
        )
        denominator = available * resource.capacity
        used = sum(
            (value.finish - value.start) * value.demand for value in intervals
        )
        utilization[resource_id] = round(used / denominator, 6) if denominator else 0.0
        peaks[resource_id] = _peak_usage(intervals)

    response = PreparationScheduleResponse(
        method="exact_branch_and_bound_resource_scheduler_v1",
        deterministic=True,
        horizon_minutes=request.horizon_minutes,
        granularity_minutes=request.granularity_minutes,
        scheduled=scheduled_values,
        unscheduled=[],
        resource_utilization=utilization,
        resource_peak_usage=peaks,
        makespan_minutes=objective[0],
        diagnostics={
            "task_count": len(request.tasks),
            "scheduled_count": len(scheduled_values),
            "unscheduled_count": 0,
            "resource_count": len(request.resources),
            "nodes_visited": nodes_visited,
            "complete_schedules_evaluated": complete_evaluated,
            "optimality": "proven_within_aligned_start_contract",
            "maximum_nodes": maximum_nodes,
            "maximum_tasks": maximum_tasks,
            "objective": "min_makespan_then_total_start_then_signature",
        },
    )
    return ExactPreparationResult(
        schedule=response,
        optimal_makespan_minutes=objective[0],
        total_start_minutes=objective[1],
        nodes_visited=nodes_visited,
        complete_schedules_evaluated=complete_evaluated,
        search_exhausted=True,
    )


def compare_heuristic_to_exact(
    request: PreparationScheduleRequest,
    *,
    maximum_tasks: int = 10,
    maximum_nodes: int = 1_000_000,
) -> PreparationScheduleComparison:
    heuristic = build_preparation_schedule(request)
    exact = exact_preparation_schedule(
        request,
        maximum_tasks=maximum_tasks,
        maximum_nodes=maximum_nodes,
    )
    heuristic_complete = (
        len(heuristic.scheduled) == len(request.tasks)
        and not heuristic.unscheduled
    )
    gap = (
        heuristic.makespan_minutes - exact.optimal_makespan_minutes
        if heuristic_complete
        else None
    )
    ratio = (
        heuristic.makespan_minutes / exact.optimal_makespan_minutes
        if heuristic_complete and exact.optimal_makespan_minutes > 0
        else None
    )
    return PreparationScheduleComparison(
        heuristic=heuristic,
        exact=exact,
        heuristic_complete=heuristic_complete,
        exact_complete=True,
        makespan_gap_minutes=gap,
        makespan_ratio=ratio,
    )
