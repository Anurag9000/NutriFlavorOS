from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_operations import PreparationOccurrenceSetDocument
from backend.engines.prep_resource_scheduler import build_preparation_schedule


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _base_payload() -> dict:
    return {
        "horizon_minutes": 180,
        "granularity_minutes": 5,
        "resources": [
            {
                "resource_id": "person",
                "capacity": 1,
                "availability_windows": [
                    {"start_minute": 0, "end_minute": 30},
                    {"start_minute": 60, "end_minute": 150},
                ],
            },
            {
                "resource_id": "burner",
                "capacity": 1,
                "availability_windows": [
                    {"start_minute": 0, "end_minute": 150}
                ],
            },
        ],
        "tasks": [
            {
                "task_id": "prep",
                "duration_minutes": 15,
                "earliest_start_minute": 0,
                "latest_finish_minute": 30,
                "priority": 3,
                "resource_demands": {"person": 1},
                "dependencies": [],
            },
            {
                "task_id": "cook-a",
                "duration_minutes": 25,
                "earliest_start_minute": 60,
                "latest_finish_minute": 120,
                "priority": 2,
                "resource_demands": {"person": 1, "burner": 1},
                "dependencies": ["prep"],
            },
            {
                "task_id": "cook-b",
                "duration_minutes": 20,
                "earliest_start_minute": 60,
                "latest_finish_minute": 150,
                "priority": 1,
                "resource_demands": {"person": 1, "burner": 1},
                "dependencies": ["prep"],
            },
        ],
    }


def _schedule(payload: dict):
    request = PreparationScheduleRequest.model_validate(payload)
    return build_preparation_schedule(request)


def _operational_signature(schedule) -> list[tuple]:
    return [
        (
            value.task_id,
            value.start_minute,
            value.finish_minute,
            tuple(sorted(value.resource_demands.items())),
            tuple(value.dependencies),
        )
        for value in schedule.scheduled
    ]


def test_resource_and_task_input_order_do_not_change_schedule():
    payload = _base_payload()
    reversed_payload = deepcopy(payload)
    reversed_payload["resources"].reverse()
    reversed_payload["tasks"].reverse()

    first = _schedule(payload)
    second = _schedule(reversed_payload)

    assert first.unscheduled == second.unscheduled == []
    assert _operational_signature(first) == _operational_signature(second)
    assert first.makespan_minutes == second.makespan_minutes
    assert first.resource_utilization == second.resource_utilization
    assert first.resource_peak_usage == second.resource_peak_usage


def test_adding_unused_resource_does_not_change_existing_task_schedule():
    payload = _base_payload()
    augmented = deepcopy(payload)
    augmented["resources"].append(
        {
            "resource_id": "unused-oven",
            "capacity": 2,
            "availability_windows": [
                {"start_minute": 0, "end_minute": 180}
            ],
        }
    )

    first = _schedule(payload)
    second = _schedule(augmented)

    assert _operational_signature(first) == _operational_signature(second)
    assert second.resource_utilization["unused-oven"] == 0.0
    assert second.resource_peak_usage["unused-oven"] == 0


def test_increasing_capacity_cannot_reduce_scheduled_task_count():
    constrained = {
        "horizon_minutes": 30,
        "granularity_minutes": 5,
        "resources": [
            {
                "resource_id": "burner",
                "capacity": 1,
                "availability_windows": [
                    {"start_minute": 0, "end_minute": 30}
                ],
            }
        ],
        "tasks": [
            {
                "task_id": "a",
                "duration_minutes": 30,
                "latest_finish_minute": 30,
                "resource_demands": {"burner": 1},
            },
            {
                "task_id": "b",
                "duration_minutes": 30,
                "latest_finish_minute": 30,
                "resource_demands": {"burner": 1},
            },
        ],
    }
    expanded = deepcopy(constrained)
    expanded["resources"][0]["capacity"] = 2

    first = _schedule(constrained)
    second = _schedule(expanded)

    assert len(second.scheduled) >= len(first.scheduled)
    assert len(first.scheduled) == 1
    assert len(second.scheduled) == 2
    assert second.resource_peak_usage["burner"] == 2


def test_expanding_availability_preserves_previously_feasible_tasks():
    constrained = {
        "horizon_minutes": 120,
        "granularity_minutes": 5,
        "resources": [
            {
                "resource_id": "oven",
                "capacity": 1,
                "availability_windows": [
                    {"start_minute": 30, "end_minute": 90}
                ],
            }
        ],
        "tasks": [
            {
                "task_id": "bake",
                "duration_minutes": 45,
                "latest_finish_minute": 100,
                "resource_demands": {"oven": 1},
            }
        ],
    }
    expanded = deepcopy(constrained)
    expanded["resources"][0]["availability_windows"] = [
        {"start_minute": 0, "end_minute": 120}
    ]

    first = _schedule(constrained)
    second = _schedule(expanded)

    assert [value.task_id for value in first.scheduled] == ["bake"]
    assert [value.task_id for value in second.scheduled] == ["bake"]
    assert second.scheduled[0].start_minute <= first.scheduled[0].start_minute


def test_occurrence_document_order_is_canonical_and_hash_stable():
    first = PreparationOccurrenceSetDocument.model_validate(
        {
            "household_id": "home",
            "occurrence_set_version": "v1",
            "duration_policy": "conservative_max",
            "occurrences": [
                {
                    "occurrence_id": "dinner",
                    "recipe_id": "recipe-b",
                    "required_finish_minute": 120,
                    "servings": 2,
                    "priority": 1,
                },
                {
                    "occurrence_id": "breakfast",
                    "recipe_id": "recipe-a",
                    "required_finish_minute": 30,
                    "servings": 1,
                    "priority": 2,
                },
            ],
        }
    )
    second_payload = first.model_dump(mode="json")
    second_payload["occurrences"].reverse()
    second = PreparationOccurrenceSetDocument.model_validate(second_payload)

    assert [value.occurrence_id for value in first.occurrences] == [
        "breakfast",
        "dinner",
    ]
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert _canonical_hash(first.model_dump(mode="json")) == _canonical_hash(
        second.model_dump(mode="json")
    )
