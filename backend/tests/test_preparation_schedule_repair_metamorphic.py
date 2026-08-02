from __future__ import annotations

from itertools import product

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair import (
    PreparationRepairStrategy,
    PreparationScheduleRepairRequest,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.engines.prep_schedule_repair import repair_preparation_schedule


def make_request(
    *,
    capacity: int,
    task_count: int,
    window_start: int = 0,
    window_end: int = 120,
    reverse_tasks: bool = False,
    add_unused_resource: bool = False,
) -> PreparationScheduleRequest:
    tasks = [
        {
            "task_id": f"task.{index + 1}",
            "duration_minutes": 5 + 5 * (index % 2),
            "earliest_start_minute": 0,
            "latest_finish_minute": 90,
            "priority": 1 + (index % 3),
            "resource_demands": {"person": 1},
            "dependencies": [],
            "metadata": {"index": index},
        }
        for index in range(task_count)
    ]
    if reverse_tasks:
        tasks.reverse()
    resources = [
        {
            "resource_id": "person",
            "label": "Available cook",
            "capacity": capacity,
            "availability_windows": [
                {"start_minute": window_start, "end_minute": window_end}
            ],
        }
    ]
    if add_unused_resource:
        resources.append(
            {
                "resource_id": "unused.counter",
                "label": "Unused counter",
                "capacity": 5,
                "availability_windows": [
                    {"start_minute": 0, "end_minute": 120}
                ],
            }
        )
    return PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 120,
            "granularity_minutes": 5,
            "resources": resources,
            "tasks": tasks,
        }
    )


def repair(
    previous: PreparationScheduleRequest,
    revised: PreparationScheduleRequest,
    *,
    strategy: PreparationRepairStrategy = PreparationRepairStrategy.GREEDY_MIN_CHANGE,
    immutable: list[str] | None = None,
):
    response = build_preparation_schedule(previous)
    assert response.unscheduled == []
    return repair_preparation_schedule(
        PreparationScheduleRepairRequest(
            previous_request=previous,
            previous_response=response,
            revised_request=revised,
            immutable_task_ids=immutable or [],
            strategy=strategy,
            allow_partial=False,
        )
    )


def objective(value) -> tuple[int, int, int, int]:
    result = value.objective
    return (
        result.unscheduled_task_count,
        result.changed_task_count,
        result.total_displacement_minutes,
        result.makespan_minutes,
    )


def response_without_unused_metric(value) -> dict:
    payload = value.response.model_dump(mode="json")
    payload["resource_utilization"].pop("unused.counter", None)
    payload["resource_peak_usage"].pop("unused.counter", None)
    return payload


def test_capacity_expansion_cannot_worsen_repair_objective():
    previous = make_request(capacity=3, task_count=4)
    constrained = repair(previous, make_request(capacity=1, task_count=4))
    expanded = repair(previous, make_request(capacity=2, task_count=4))

    assert objective(expanded) <= objective(constrained)


def test_availability_expansion_cannot_worsen_repair_objective():
    previous = make_request(capacity=1, task_count=3)
    narrow = repair(
        previous,
        make_request(capacity=1, task_count=3, window_start=30, window_end=120),
    )
    wider = repair(
        previous,
        make_request(capacity=1, task_count=3, window_start=15, window_end=120),
    )

    assert objective(wider) <= objective(narrow)


def test_unused_resource_does_not_change_task_placements_or_objective():
    previous = make_request(capacity=2, task_count=3)
    baseline = repair(previous, make_request(capacity=1, task_count=3))
    with_unused = repair(
        previous,
        make_request(
            capacity=1,
            task_count=3,
            add_unused_resource=True,
        ),
    )

    assert objective(with_unused) == objective(baseline)
    assert [
        (value.task_id, value.start_minute, value.finish_minute)
        for value in with_unused.response.scheduled
    ] == [
        (value.task_id, value.start_minute, value.finish_minute)
        for value in baseline.response.scheduled
    ]
    assert response_without_unused_metric(with_unused) == baseline.response.model_dump(
        mode="json"
    )


def test_revised_task_order_does_not_change_repair_result():
    previous = make_request(capacity=3, task_count=4)
    ordered = repair(previous, make_request(capacity=1, task_count=4))
    reversed_input = repair(
        previous,
        make_request(capacity=1, task_count=4, reverse_tasks=True),
    )

    assert objective(ordered) == objective(reversed_input)
    assert ordered.response.model_dump(mode="json") == reversed_input.response.model_dump(
        mode="json"
    )
    assert ordered.repaired_response_hash == reversed_input.repaired_response_hash


def test_immutable_tasks_remain_at_exact_prior_starts_across_capacity_changes():
    previous = make_request(capacity=3, task_count=4)
    previous_response = build_preparation_schedule(previous)
    immutable = ["task.1", "task.2"]
    result = repair(
        previous,
        make_request(capacity=2, task_count=4),
        immutable=immutable,
    )
    prior_starts = {
        value.task_id: value.start_minute for value in previous_response.scheduled
    }
    repaired_starts = {
        value.task_id: value.start_minute for value in result.response.scheduled
    }

    for task_id in immutable:
        assert repaired_starts[task_id] == prior_starts[task_id]
        assert task_id in result.preserved_task_ids


def test_bounded_exact_is_no_worse_than_greedy_across_small_generated_cases():
    for task_count, previous_capacity, revised_capacity, window_start in product(
        [2, 3, 4],
        [2, 3],
        [1, 2],
        [0, 10],
    ):
        previous = make_request(
            capacity=previous_capacity,
            task_count=task_count,
        )
        revised = make_request(
            capacity=revised_capacity,
            task_count=task_count,
            window_start=window_start,
        )
        greedy = repair(
            previous,
            revised,
            strategy=PreparationRepairStrategy.GREEDY_MIN_CHANGE,
        )
        exact = repair(
            previous,
            revised,
            strategy=PreparationRepairStrategy.BOUNDED_EXACT_MIN_CHANGE,
        )
        assert objective(exact) <= objective(greedy), (
            task_count,
            previous_capacity,
            revised_capacity,
            window_start,
            objective(greedy),
            objective(exact),
        )
