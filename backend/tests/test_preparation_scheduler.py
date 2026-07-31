from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleRequest,
    PreparationTask,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule


def test_scheduler_is_deterministic_and_serializes_single_capacity_resource():
    request = PreparationScheduleRequest(
        horizon_minutes=180,
        granularity_minutes=5,
        resources=[PreparationResource(resource_id="oven", capacity=1)],
        tasks=[
            PreparationTask(
                task_id="roast",
                duration_minutes=60,
                latest_finish_minute=120,
                priority=1,
                resource_demands={"oven": 1},
            ),
            PreparationTask(
                task_id="bake",
                duration_minutes=45,
                latest_finish_minute=120,
                priority=5,
                resource_demands={"oven": 1},
            ),
        ],
    )

    first = build_preparation_schedule(request)
    second = build_preparation_schedule(request)

    assert first == second
    assert [(task.task_id, task.start_minute, task.finish_minute) for task in first.scheduled] == [
        ("bake", 0, 45),
        ("roast", 45, 105),
    ]
    assert first.unscheduled == []
    assert first.resource_peak_usage == {"oven": 1}
    assert first.resource_utilization["oven"] == pytest.approx(105 / 180)


def test_parallel_capacity_allows_overlap_without_exceeding_peak():
    result = build_preparation_schedule(
        PreparationScheduleRequest(
            horizon_minutes=60,
            granularity_minutes=1,
            resources=[PreparationResource(resource_id="burner", capacity=2)],
            tasks=[
                PreparationTask(
                    task_id="pot-a",
                    duration_minutes=30,
                    resource_demands={"burner": 1},
                ),
                PreparationTask(
                    task_id="pot-b",
                    duration_minutes=30,
                    resource_demands={"burner": 1},
                ),
            ],
        )
    )

    assert [(task.task_id, task.start_minute) for task in result.scheduled] == [
        ("pot-a", 0),
        ("pot-b", 0),
    ]
    assert result.resource_peak_usage["burner"] == 2
    assert result.resource_utilization["burner"] == pytest.approx(0.5)


def test_missing_resources_and_excessive_demands_are_explicit():
    result = build_preparation_schedule(
        PreparationScheduleRequest(
            horizon_minutes=120,
            resources=[PreparationResource(resource_id="oven", capacity=1)],
            tasks=[
                PreparationTask(
                    task_id="freeze",
                    duration_minutes=20,
                    resource_demands={"freezer": 1},
                ),
                PreparationTask(
                    task_id="double-oven",
                    duration_minutes=20,
                    resource_demands={"oven": 2},
                ),
            ],
        )
    )

    by_id = {task.task_id: task for task in result.unscheduled}
    assert by_id["freeze"].reason_code == "missing_resource"
    assert by_id["freeze"].missing_resources == ["freezer"]
    assert by_id["double-oven"].reason_code == "capacity_exceeded"
    assert by_id["double-oven"].capacity_violations == {
        "oven": {"requested": 2, "capacity": 1}
    }


def test_availability_windows_and_deadlines_are_respected():
    result = build_preparation_schedule(
        PreparationScheduleRequest(
            horizon_minutes=120,
            granularity_minutes=5,
            resources=[
                PreparationResource(
                    resource_id="prep-counter",
                    capacity=1,
                    available_from_minute=15,
                    available_until_minute=75,
                )
            ],
            tasks=[
                PreparationTask(
                    task_id="chop",
                    duration_minutes=20,
                    earliest_start_minute=1,
                    latest_finish_minute=60,
                    resource_demands={"prep-counter": 1},
                ),
                PreparationTask(
                    task_id="long-task",
                    duration_minutes=70,
                    earliest_start_minute=0,
                    latest_finish_minute=60,
                    resource_demands={"prep-counter": 1},
                ),
            ],
        )
    )

    assert [(task.task_id, task.start_minute, task.finish_minute) for task in result.scheduled] == [
        ("chop", 15, 35)
    ]
    assert result.unscheduled[0].task_id == "long-task"
    assert result.unscheduled[0].reason_code == "window_too_short"


def test_tasks_without_declared_resources_do_not_gain_invented_requirements():
    result = build_preparation_schedule(
        PreparationScheduleRequest(
            horizon_minutes=30,
            granularity_minutes=5,
            resources=[],
            tasks=[
                PreparationTask(
                    task_id="manual-review",
                    duration_minutes=10,
                    earliest_start_minute=3,
                    metadata={"source": "human-declared"},
                )
            ],
        )
    )

    assert result.scheduled[0].start_minute == 5
    assert result.scheduled[0].resource_demands == {}
    assert result.resource_utilization == {}


def test_duplicate_identifiers_are_rejected_before_scheduling():
    with pytest.raises(ValidationError, match="resource_id values must be unique"):
        PreparationScheduleRequest(
            resources=[
                PreparationResource(resource_id="oven"),
                PreparationResource(resource_id="oven"),
            ]
        )

    with pytest.raises(ValidationError, match="task_id values must be unique"):
        PreparationScheduleRequest(
            tasks=[
                PreparationTask(task_id="same", duration_minutes=10),
                PreparationTask(task_id="same", duration_minutes=20),
            ]
        )
