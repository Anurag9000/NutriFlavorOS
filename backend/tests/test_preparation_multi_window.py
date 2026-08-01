from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domain.preparation import PreparationScheduleRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.research.exact_preparation_scheduler import (
    ExactPreparationInfeasible,
    compare_heuristic_to_exact,
    exact_preparation_schedule,
)


def request_with(
    *,
    resources: list[dict],
    tasks: list[dict],
    horizon: int = 180,
) -> PreparationScheduleRequest:
    return PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": horizon,
            "granularity_minutes": 5,
            "resources": resources,
            "tasks": tasks,
        }
    )


def resource(
    identifier: str,
    windows: list[tuple[int, int]],
    *,
    capacity: int = 1,
) -> dict:
    return {
        "resource_id": identifier,
        "label": identifier.title(),
        "capacity": capacity,
        "availability_windows": [
            {"start_minute": start, "end_minute": end}
            for start, end in windows
        ],
    }


def task(
    identifier: str,
    duration: int,
    demands: dict[str, int],
    *,
    earliest: int = 0,
    latest: int = 180,
    dependencies: list[str] | None = None,
    priority: int = 0,
) -> dict:
    return {
        "task_id": identifier,
        "duration_minutes": duration,
        "earliest_start_minute": earliest,
        "latest_finish_minute": latest,
        "priority": priority,
        "resource_demands": demands,
        "dependencies": dependencies or [],
        "metadata": {},
    }


def test_task_skips_calendar_gap_and_uses_second_window():
    request = request_with(
        resources=[resource("burner", [(0, 20), (60, 120)])],
        tasks=[task("simmer", 30, {"burner": 1}, latest=120)],
        horizon=120,
    )
    schedule = build_preparation_schedule(request)
    assert schedule.unscheduled == []
    assert [(value.task_id, value.start_minute, value.finish_minute) for value in schedule.scheduled] == [
        ("simmer", 60, 90)
    ]
    assert schedule.diagnostics["resource_window_counts"] == {"burner": 2}


def test_task_cannot_span_a_gap_even_when_outer_bounds_are_long_enough():
    request = request_with(
        resources=[resource("oven", [(0, 20), (30, 50)])],
        tasks=[task("bake", 30, {"oven": 1}, latest=50)],
        horizon=50,
    )
    schedule = build_preparation_schedule(request)
    assert schedule.scheduled == []
    assert len(schedule.unscheduled) == 1
    assert schedule.unscheduled[0].task_id == "bake"
    assert schedule.unscheduled[0].reason_code == "resource_availability_infeasible"
    with pytest.raises(ExactPreparationInfeasible):
        exact_preparation_schedule(request)


def test_multiple_resources_require_one_common_containing_window():
    request = request_with(
        resources=[
            resource("person", [(0, 30), (60, 120)]),
            resource("burner", [(20, 80), (100, 160)]),
        ],
        tasks=[task("cook", 20, {"person": 1, "burner": 1}, latest=160)],
        horizon=160,
    )
    schedule = build_preparation_schedule(request)
    assert schedule.unscheduled == []
    # The first feasible common interval is [100, 120], not a span across gaps.
    assert schedule.scheduled[0].start_minute == 100
    assert schedule.scheduled[0].finish_minute == 120


def test_utilization_denominator_sums_only_declared_available_minutes():
    request = request_with(
        resources=[resource("burner", [(0, 20), (60, 100)], capacity=2)],
        tasks=[
            task("first", 20, {"burner": 1}, latest=20, priority=2),
            task("second", 20, {"burner": 2}, earliest=60, latest=100, priority=1),
        ],
        horizon=100,
    )
    schedule = build_preparation_schedule(request)
    assert schedule.unscheduled == []
    # Used capacity-minutes = 20*1 + 20*2 = 60.
    # Available capacity-minutes = (20 + 40) * 2 = 120.
    assert schedule.resource_utilization["burner"] == 0.5
    assert schedule.resource_peak_usage["burner"] == 2


def test_exact_and_heuristic_share_multi_window_contract_and_are_deterministic():
    request = request_with(
        resources=[
            resource("person", [(0, 35), (60, 150)]),
            resource("burner", [(0, 150)]),
        ],
        tasks=[
            task("prep", 15, {"person": 1}, latest=35, priority=3),
            task(
                "cook-a",
                25,
                {"person": 1, "burner": 1},
                earliest=60,
                latest=120,
                dependencies=["prep"],
                priority=2,
            ),
            task(
                "cook-b",
                20,
                {"person": 1, "burner": 1},
                earliest=60,
                latest=150,
                dependencies=["prep"],
                priority=1,
            ),
        ],
        horizon=150,
    )
    first = compare_heuristic_to_exact(request, maximum_tasks=10, maximum_nodes=200_000)
    second = compare_heuristic_to_exact(request, maximum_tasks=10, maximum_nodes=200_000)

    assert first.heuristic_complete is True
    assert first.exact_complete is True
    assert first.makespan_gap_minutes == 0
    assert first.makespan_ratio == 1.0
    assert first.heuristic.model_dump() == second.heuristic.model_dump()
    assert first.exact.schedule.model_dump() == second.exact.schedule.model_dump()
    assert first.exact.optimal_makespan_minutes == 105
    assert first.heuristic.diagnostics["resource_window_counts"] == {
        "burner": 1,
        "person": 2,
    }
    assert first.exact.schedule.diagnostics["resource_window_counts"] == {
        "burner": 1,
        "person": 2,
    }


def test_explicit_windows_reject_legacy_overlap_and_horizon_drift():
    with pytest.raises(ValidationError, match="cannot be combined"):
        request_with(
            resources=[
                {
                    **resource("burner", [(0, 30)]),
                    "available_from_minute": 5,
                }
            ],
            tasks=[],
            horizon=60,
        )

    with pytest.raises(ValidationError, match="cannot overlap"):
        request_with(
            resources=[resource("burner", [(0, 30), (20, 40)])],
            tasks=[],
            horizon=60,
        )

    with pytest.raises(ValidationError, match="exceed the scheduling horizon"):
        request_with(
            resources=[resource("burner", [(0, 61)])],
            tasks=[],
            horizon=60,
        )


def test_adjacent_windows_remain_distinct_and_cannot_host_a_cross_boundary_task():
    request = request_with(
        resources=[resource("burner", [(0, 20), (20, 40)])],
        tasks=[task("continuous-task", 30, {"burner": 1}, latest=40)],
        horizon=40,
    )
    schedule = build_preparation_schedule(request)
    assert schedule.scheduled == []
    assert schedule.unscheduled[0].reason_code == "resource_availability_infeasible"
