from __future__ import annotations

import copy

import pytest

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair import (
    PreparationRepairStrategy,
    PreparationScheduleRepairRequest,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.engines.prep_schedule_repair import (
    PreparationRepairError,
    repair_preparation_schedule,
)


def request(
    *,
    capacity: int = 1,
    windows: list[tuple[int, int]] | None = None,
    tasks: list[dict] | None = None,
) -> PreparationScheduleRequest:
    return PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 120,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "person",
                    "label": "Available cook",
                    "capacity": capacity,
                    "availability_windows": [
                        {"start_minute": start, "end_minute": end}
                        for start, end in (windows or [(0, 120)])
                    ],
                }
            ],
            "tasks": tasks
            or [
                {
                    "task_id": "task.a",
                    "duration_minutes": 10,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 60,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {"label": "A"},
                },
                {
                    "task_id": "task.b",
                    "duration_minutes": 10,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 60,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {"label": "B"},
                },
            ],
        }
    )


def repair_request(
    previous: PreparationScheduleRequest,
    revised: PreparationScheduleRequest | None = None,
    *,
    immutable: list[str] | None = None,
    strategy: PreparationRepairStrategy = PreparationRepairStrategy.GREEDY_MIN_CHANGE,
    allow_partial: bool = False,
    exact_task_limit: int = 9,
) -> PreparationScheduleRepairRequest:
    response = build_preparation_schedule(previous)
    assert not response.unscheduled
    return PreparationScheduleRepairRequest(
        previous_request=previous,
        previous_response=response,
        revised_request=revised or previous,
        immutable_task_ids=immutable or [],
        strategy=strategy,
        allow_partial=allow_partial,
        exact_task_limit=exact_task_limit,
    )


def starts(result) -> dict[str, int]:
    return {value.task_id: value.start_minute for value in result.response.scheduled}


def objective_tuple(result) -> tuple[int, int, int, int]:
    value = result.objective
    return (
        value.unscheduled_task_count,
        value.changed_task_count,
        value.total_displacement_minutes,
        value.makespan_minutes,
    )


def test_identity_repair_preserves_every_task_and_is_hash_deterministic():
    previous = request()
    first = repair_preparation_schedule(repair_request(previous))
    second = repair_preparation_schedule(repair_request(previous))

    assert first.complete is True
    assert first.preserved_task_ids == ["task.a", "task.b"]
    assert first.moved_tasks == []
    assert first.added_task_ids == []
    assert first.removed_task_ids == []
    assert first.unscheduled_task_ids == []
    assert first.objective.changed_task_count == 0
    assert first.objective.total_displacement_minutes == 0
    assert first.response.model_dump(mode="json") == second.response.model_dump(mode="json")
    assert first.previous_schedule_hash == second.previous_schedule_hash
    assert first.revised_request_hash == second.revised_request_hash
    assert first.repaired_response_hash == second.repaired_response_hash


def test_reordered_tasks_and_resources_produce_the_same_repair_output():
    previous = request(capacity=2)
    revised_payload = previous.model_dump(mode="json")
    revised_payload["tasks"] = list(reversed(revised_payload["tasks"]))
    revised_payload["resources"] = list(reversed(revised_payload["resources"]))
    revised = PreparationScheduleRequest.model_validate(revised_payload)

    ordered = repair_preparation_schedule(repair_request(previous, previous))
    reordered = repair_preparation_schedule(repair_request(previous, revised))

    assert ordered.response.model_dump(mode="json") == reordered.response.model_dump(mode="json")
    assert ordered.repaired_response_hash == reordered.repaired_response_hash
    assert starts(ordered) == starts(reordered)


def test_capacity_reduction_moves_only_one_task_with_minimum_displacement():
    previous = request(capacity=2)
    revised = request(capacity=1)
    result = repair_preparation_schedule(repair_request(previous, revised))

    assert result.complete is True
    assert len(result.preserved_task_ids) == 1
    assert len(result.moved_tasks) == 1
    movement = result.moved_tasks[0]
    assert movement.previous_start_minute == 0
    assert movement.repaired_start_minute == 10
    assert abs(movement.displacement_minutes) == 10
    assert result.objective.changed_task_count == 1
    assert result.objective.total_displacement_minutes == 10
    assert sorted(starts(result).values()) == [0, 10]


def test_immutable_task_is_pinned_exactly_while_other_work_moves():
    previous = request(capacity=2)
    revised = request(capacity=1)
    prior = build_preparation_schedule(previous)
    immutable_id = sorted(value.task_id for value in prior.scheduled)[0]
    prior_start = next(
        value.start_minute for value in prior.scheduled if value.task_id == immutable_id
    )

    result = repair_preparation_schedule(
        PreparationScheduleRepairRequest(
            previous_request=previous,
            previous_response=prior,
            revised_request=revised,
            immutable_task_ids=[immutable_id],
        )
    )

    assert immutable_id in result.immutable_task_ids
    assert starts(result)[immutable_id] == prior_start
    assert immutable_id in result.preserved_task_ids
    assert all(value.task_id != immutable_id for value in result.moved_tasks)


def test_removed_changed_or_infeasible_immutable_tasks_fail_closed():
    previous = request()
    previous_response = build_preparation_schedule(previous)

    removed_payload = previous.model_dump(mode="json")
    removed_payload["tasks"] = [
        value for value in removed_payload["tasks"] if value["task_id"] != "task.a"
    ]
    with pytest.raises(PreparationRepairError) as removed:
        repair_preparation_schedule(
            PreparationScheduleRepairRequest(
                previous_request=previous,
                previous_response=previous_response,
                revised_request=PreparationScheduleRequest.model_validate(removed_payload),
                immutable_task_ids=["task.a"],
            )
        )
    assert removed.value.code == "immutable_task_removed"

    changed_payload = previous.model_dump(mode="json")
    next(value for value in changed_payload["tasks"] if value["task_id"] == "task.a")[
        "duration_minutes"
    ] = 15
    with pytest.raises(PreparationRepairError) as changed:
        repair_preparation_schedule(
            PreparationScheduleRepairRequest(
                previous_request=previous,
                previous_response=previous_response,
                revised_request=PreparationScheduleRequest.model_validate(changed_payload),
                immutable_task_ids=["task.a"],
            )
        )
    assert changed.value.code == "immutable_task_changed"

    infeasible = request(windows=[(20, 120)])
    with pytest.raises(PreparationRepairError) as blocked:
        repair_preparation_schedule(
            PreparationScheduleRepairRequest(
                previous_request=previous,
                previous_response=previous_response,
                revised_request=infeasible,
                immutable_task_ids=["task.a"],
            )
        )
    assert blocked.value.code == "immutable_task_infeasible"


def test_immutable_dependency_closure_is_required():
    previous = request(
        tasks=[
            {
                "task_id": "task.a",
                "duration_minutes": 10,
                "earliest_start_minute": 0,
                "latest_finish_minute": 60,
                "priority": 1,
                "resource_demands": {"person": 1},
                "dependencies": [],
                "metadata": {},
            },
            {
                "task_id": "task.b",
                "duration_minutes": 10,
                "earliest_start_minute": 0,
                "latest_finish_minute": 60,
                "priority": 1,
                "resource_demands": {"person": 1},
                "dependencies": ["task.a"],
                "metadata": {},
            },
        ]
    )
    with pytest.raises(PreparationRepairError) as exc:
        repair_preparation_schedule(repair_request(previous, immutable=["task.b"]))
    assert exc.value.code == "immutable_dependency_not_pinned"
    assert exc.value.details["tasks"] == {"task.b": ["task.a"]}


def test_dependency_chronology_is_preserved_after_repair():
    previous = request(
        capacity=2,
        tasks=[
            {
                "task_id": "task.a",
                "duration_minutes": 10,
                "earliest_start_minute": 0,
                "latest_finish_minute": 80,
                "priority": 1,
                "resource_demands": {"person": 1},
                "dependencies": [],
                "metadata": {},
            },
            {
                "task_id": "task.b",
                "duration_minutes": 10,
                "earliest_start_minute": 0,
                "latest_finish_minute": 80,
                "priority": 1,
                "resource_demands": {"person": 1},
                "dependencies": ["task.a"],
                "metadata": {},
            },
            {
                "task_id": "task.c",
                "duration_minutes": 10,
                "earliest_start_minute": 0,
                "latest_finish_minute": 80,
                "priority": 1,
                "resource_demands": {"person": 1},
                "dependencies": ["task.b"],
                "metadata": {},
            },
        ],
    )
    revised = request(capacity=1, tasks=previous.model_dump(mode="json")["tasks"])
    result = repair_preparation_schedule(repair_request(previous, revised))
    by_id = {value.task_id: value for value in result.response.scheduled}

    assert by_id["task.a"].finish_minute <= by_id["task.b"].start_minute
    assert by_id["task.b"].finish_minute <= by_id["task.c"].start_minute


def test_partial_mode_reports_explicit_unscheduled_work_and_complete_mode_rejects():
    previous = request()
    revised_payload = previous.model_dump(mode="json")
    revised_payload["resources"] = []
    revised = PreparationScheduleRequest.model_validate(revised_payload)

    partial = repair_preparation_schedule(
        repair_request(previous, revised, allow_partial=True)
    )
    assert partial.complete is False
    assert partial.unscheduled_task_ids == ["task.a", "task.b"]
    assert partial.objective.unscheduled_task_count == 2
    assert all(
        value.reason_code == "missing_resource"
        for value in partial.response.unscheduled
    )
    assert any("cannot be treated as an executable" in value for value in partial.warnings)

    with pytest.raises(PreparationRepairError) as exc:
        repair_preparation_schedule(repair_request(previous, revised))
    assert exc.value.code == "repair_infeasible"
    assert exc.value.details["unscheduled_task_ids"] == ["task.a", "task.b"]


def test_added_and_removed_tasks_are_reported_without_rewriting_previous_schedule():
    previous = request()
    previous_snapshot = copy.deepcopy(previous.model_dump(mode="json"))
    revised_payload = previous.model_dump(mode="json")
    revised_payload["tasks"] = [
        value for value in revised_payload["tasks"] if value["task_id"] != "task.b"
    ]
    revised_payload["tasks"].append(
        {
            "task_id": "task.c",
            "duration_minutes": 5,
            "earliest_start_minute": 0,
            "latest_finish_minute": 60,
            "priority": 1,
            "resource_demands": {"person": 1},
            "dependencies": [],
            "metadata": {"label": "C"},
        }
    )
    revised = PreparationScheduleRequest.model_validate(revised_payload)
    result = repair_preparation_schedule(repair_request(previous, revised))

    assert result.added_task_ids == ["task.c"]
    assert result.removed_task_ids == ["task.b"]
    assert result.objective.changed_task_count >= 2
    assert previous.model_dump(mode="json") == previous_snapshot


def test_bounded_exact_result_is_not_worse_than_greedy_on_small_instance():
    previous = request(capacity=2)
    revised = request(capacity=1)
    greedy = repair_preparation_schedule(
        repair_request(
            previous,
            revised,
            strategy=PreparationRepairStrategy.GREEDY_MIN_CHANGE,
        )
    )
    exact = repair_preparation_schedule(
        repair_request(
            previous,
            revised,
            strategy=PreparationRepairStrategy.BOUNDED_EXACT_MIN_CHANGE,
        )
    )

    assert objective_tuple(exact) <= objective_tuple(greedy)
    assert exact.diagnostics.strategy == PreparationRepairStrategy.BOUNDED_EXACT_MIN_CHANGE
    assert exact.diagnostics.explored_states > 0


def test_exact_task_limit_falls_back_deterministically_to_greedy():
    previous = request(capacity=2)
    revised = request(capacity=1)
    result = repair_preparation_schedule(
        repair_request(
            previous,
            revised,
            strategy=PreparationRepairStrategy.BOUNDED_EXACT_MIN_CHANGE,
            exact_task_limit=1,
        )
    )
    assert result.complete is True
    assert result.diagnostics.exact_search_truncated is True
    assert any("used the deterministic greedy repair" in value for value in result.warnings)
