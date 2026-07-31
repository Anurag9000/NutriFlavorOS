from __future__ import annotations

import pytest

from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleRequest,
    PreparationTask,
)
from backend.research.exact_preparation_scheduler import (
    ExactPreparationInfeasible,
    ExactPreparationSearchLimit,
    compare_heuristic_to_exact,
    exact_preparation_schedule,
)


def test_exact_scheduler_proves_optimal_parallel_makespan():
    request = PreparationScheduleRequest(
        horizon_minutes=60,
        granularity_minutes=5,
        resources=[
            PreparationResource(resource_id="counter", capacity=1),
            PreparationResource(resource_id="oven", capacity=1),
        ],
        tasks=[
            PreparationTask(
                task_id="mix",
                duration_minutes=10,
                resource_demands={"counter": 1},
            ),
            PreparationTask(
                task_id="preheat",
                duration_minutes=15,
                resource_demands={"oven": 1},
            ),
            PreparationTask(
                task_id="bake",
                duration_minutes=20,
                resource_demands={"oven": 1},
                dependencies=["mix", "preheat"],
            ),
        ],
    )

    result = exact_preparation_schedule(request)
    assert result.schedule.method == "exact_branch_and_bound_resource_scheduler_v1"
    assert result.optimal_makespan_minutes == 35
    assert [(value.task_id, value.start_minute, value.finish_minute) for value in result.schedule.scheduled] == [
        ("mix", 0, 10),
        ("preheat", 0, 15),
        ("bake", 15, 35),
    ]
    assert result.schedule.resource_peak_usage == {"counter": 1, "oven": 1}
    assert result.complete_schedules_evaluated >= 1
    assert result.search_exhausted is True
    assert result.schedule.diagnostics["optimality"] == "proven_within_aligned_start_contract"


def test_exact_scheduler_handles_cumulative_parallel_capacity():
    request = PreparationScheduleRequest(
        horizon_minutes=30,
        granularity_minutes=1,
        resources=[PreparationResource(resource_id="burner", capacity=2)],
        tasks=[
            PreparationTask(
                task_id="pot-a",
                duration_minutes=10,
                resource_demands={"burner": 1},
            ),
            PreparationTask(
                task_id="pot-b",
                duration_minutes=10,
                resource_demands={"burner": 1},
            ),
            PreparationTask(
                task_id="pot-c",
                duration_minutes=10,
                resource_demands={"burner": 1},
            ),
        ],
    )
    result = exact_preparation_schedule(request)
    assert result.optimal_makespan_minutes == 20
    assert result.schedule.resource_peak_usage["burner"] == 2


def test_exact_scheduler_reports_infeasible_complete_schedule():
    request = PreparationScheduleRequest(
        horizon_minutes=10,
        granularity_minutes=1,
        resources=[PreparationResource(resource_id="oven", capacity=1)],
        tasks=[
            PreparationTask(
                task_id="a",
                duration_minutes=10,
                resource_demands={"oven": 1},
            ),
            PreparationTask(
                task_id="b",
                duration_minutes=10,
                resource_demands={"oven": 1},
            ),
        ],
    )
    with pytest.raises(ExactPreparationInfeasible, match="no complete aligned"):
        exact_preparation_schedule(request)


def test_exact_scheduler_rejects_missing_resource_and_task_limit():
    missing = PreparationScheduleRequest(
        horizon_minutes=20,
        tasks=[
            PreparationTask(
                task_id="freeze",
                duration_minutes=5,
                resource_demands={"freezer": 1},
            )
        ],
    )
    with pytest.raises(ExactPreparationInfeasible, match="missing resources"):
        exact_preparation_schedule(missing)

    too_many = PreparationScheduleRequest(
        horizon_minutes=20,
        tasks=[
            PreparationTask(task_id=f"task-{index}", duration_minutes=1)
            for index in range(3)
        ],
    )
    with pytest.raises(ValueError, match="at most 2 tasks"):
        exact_preparation_schedule(too_many, maximum_tasks=2)


def test_exact_scheduler_stops_at_explicit_node_budget():
    request = PreparationScheduleRequest(
        horizon_minutes=20,
        granularity_minutes=1,
        tasks=[
            PreparationTask(task_id="a", duration_minutes=1),
            PreparationTask(task_id="b", duration_minutes=1),
        ],
    )
    with pytest.raises(ExactPreparationSearchLimit, match="exceeded 1 nodes"):
        exact_preparation_schedule(request, maximum_nodes=1)


def test_heuristic_comparison_reports_proven_gap_contract():
    request = PreparationScheduleRequest(
        horizon_minutes=60,
        granularity_minutes=5,
        resources=[PreparationResource(resource_id="oven", capacity=1)],
        tasks=[
            PreparationTask(
                task_id="a",
                duration_minutes=10,
                resource_demands={"oven": 1},
            ),
            PreparationTask(
                task_id="b",
                duration_minutes=15,
                resource_demands={"oven": 1},
            ),
        ],
    )
    comparison = compare_heuristic_to_exact(request)
    assert comparison.heuristic_complete is True
    assert comparison.exact_complete is True
    assert comparison.makespan_gap_minutes == 0
    assert comparison.makespan_ratio == pytest.approx(1.0)
    assert comparison.heuristic.makespan_minutes >= comparison.exact.optimal_makespan_minutes
