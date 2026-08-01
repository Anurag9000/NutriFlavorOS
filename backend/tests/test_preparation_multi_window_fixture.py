from __future__ import annotations

import json
from pathlib import Path

from backend.domain.preparation import PreparationScheduleRequest
from backend.research.exact_preparation_scheduler import compare_heuristic_to_exact


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "benchmarks" / "preparation_scheduler_multi_window.json"


def test_canonical_multi_window_fixture_is_deterministic_and_exact_optimal():
    request = PreparationScheduleRequest.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )
    first = compare_heuristic_to_exact(
        request,
        maximum_tasks=10,
        maximum_nodes=500_000,
    )
    second = compare_heuristic_to_exact(
        request,
        maximum_tasks=10,
        maximum_nodes=500_000,
    )

    assert first.heuristic_complete is True
    assert first.exact_complete is True
    assert first.makespan_gap_minutes == 0
    assert first.makespan_ratio == 1.0
    assert first.heuristic.model_dump(mode="json") == second.heuristic.model_dump(
        mode="json"
    )
    assert first.exact.schedule.model_dump(mode="json") == second.exact.schedule.model_dump(
        mode="json"
    )
    assert first.heuristic.diagnostics["resource_window_counts"] == {
        "burner": 1,
        "oven": 2,
        "person": 2,
    }
    assert first.exact.schedule.diagnostics["resource_window_counts"] == {
        "burner": 1,
        "oven": 2,
        "person": 2,
    }
    assert [value.task_id for value in first.heuristic.scheduled] == [
        "prep",
        "cook-a",
        "bake",
        "cook-b",
    ]
    assert all(
        value.start_minute >= 60
        for value in first.heuristic.scheduled
        if value.task_id in {"cook-a", "cook-b"}
    )
    bake = next(value for value in first.heuristic.scheduled if value.task_id == "bake")
    assert (bake.start_minute, bake.finish_minute) == (90, 120)


def test_canonical_fixture_round_trip_is_stable():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    request = PreparationScheduleRequest.model_validate(raw)
    reparsed = PreparationScheduleRequest.model_validate(
        request.model_dump(mode="json")
    )
    assert reparsed == request
