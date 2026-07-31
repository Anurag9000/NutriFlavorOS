from __future__ import annotations

from backend.domain.preparation import PreparationScheduleRequest
from scripts.benchmark_preparation_schedulers import (
    benchmark_preparation_schedulers,
    regression_failures,
    request_fingerprint,
)


def fixture_request() -> PreparationScheduleRequest:
    return PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 60,
            "granularity_minutes": 5,
            "resources": [
                {"resource_id": "counter", "capacity": 1},
                {"resource_id": "oven", "capacity": 1},
            ],
            "tasks": [
                {
                    "task_id": "mix",
                    "duration_minutes": 10,
                    "resource_demands": {"counter": 1},
                    "dependencies": [],
                },
                {
                    "task_id": "preheat",
                    "duration_minutes": 15,
                    "resource_demands": {"oven": 1},
                    "dependencies": [],
                },
                {
                    "task_id": "bake",
                    "duration_minutes": 20,
                    "resource_demands": {"oven": 1},
                    "dependencies": ["mix", "preheat"],
                },
            ],
        }
    )


def test_preparation_benchmark_is_deterministic_and_exact():
    request = fixture_request()
    first = benchmark_preparation_schedulers(
        request,
        heuristic_repeats=2,
        maximum_tasks=10,
        maximum_nodes=100_000,
    )
    second = benchmark_preparation_schedulers(
        request,
        heuristic_repeats=2,
        maximum_tasks=10,
        maximum_nodes=100_000,
    )
    assert first["protocol_version"] == "preparation_scheduler_exact_comparison_v1"
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["input_fingerprint"] == request_fingerprint(request)
    assert first["heuristic"]["deterministic"] is True
    assert first["heuristic"]["complete"] is True
    assert first["exact"]["status"] == "ok"
    assert first["exact"]["optimal_makespan_minutes"] == 35
    assert first["comparison"]["makespan_gap_minutes"] == 0
    assert first["comparison"]["makespan_ratio"] == 1


def test_preparation_benchmark_regression_gates():
    report = benchmark_preparation_schedulers(
        fixture_request(),
        heuristic_repeats=2,
        maximum_nodes=100_000,
    )
    assert regression_failures(
        report,
        require_heuristic_complete=True,
        require_exact_optimal=True,
        maximum_gap_minutes=0,
        maximum_exact_nodes=100_000,
    ) == []
    failures = regression_failures(
        report,
        require_heuristic_complete=True,
        require_exact_optimal=True,
        maximum_gap_minutes=0,
        maximum_exact_nodes=1,
    )
    assert any("visited" in value for value in failures)


def test_preparation_benchmark_reports_exact_infeasibility():
    request = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 10,
            "granularity_minutes": 1,
            "resources": [{"resource_id": "oven", "capacity": 1}],
            "tasks": [
                {
                    "task_id": "a",
                    "duration_minutes": 10,
                    "resource_demands": {"oven": 1},
                },
                {
                    "task_id": "b",
                    "duration_minutes": 10,
                    "resource_demands": {"oven": 1},
                },
            ],
        }
    )
    report = benchmark_preparation_schedulers(request)
    assert report["heuristic"]["complete"] is False
    assert report["exact"]["status"] == "infeasible"
    failures = regression_failures(
        report,
        require_heuristic_complete=True,
        require_exact_optimal=True,
        maximum_gap_minutes=0,
        maximum_exact_nodes=None,
    )
    assert any("heuristic did not" in value for value in failures)
    assert any("exact solver did not" in value for value in failures)
