from __future__ import annotations

from backend.domain.preparation_repair import (
    PreparationRepairStrategy,
    PreparationScheduleRepairResult,
)


def _result_document() -> dict:
    return {
        "response": {
            "method": "deterministic_dependency_aware_resource_scheduler_v2",
            "deterministic": True,
            "horizon_minutes": 60,
            "granularity_minutes": 5,
            "scheduled": [],
            "unscheduled": [],
            "resource_utilization": {},
            "resource_peak_usage": {},
            "makespan_minutes": 0,
            "diagnostics": {},
        },
        "complete": True,
        "immutable_task_ids": [],
        "preserved_task_ids": [],
        "moved_tasks": [],
        "added_task_ids": [],
        "removed_task_ids": [],
        "unscheduled_task_ids": [],
        "objective": {
            "unscheduled_task_count": 0,
            "changed_task_count": 0,
            "total_displacement_minutes": 0,
            "makespan_minutes": 0,
            "weighted_value": 0.0,
        },
        "diagnostics": {
            "strategy": "greedy_min_change",
            "deterministic": True,
            "explored_states": 0,
            "pruned_states": 0,
            "candidate_placements_considered": 0,
            "preserved_attempt_count": 0,
            "exact_search_truncated": False,
            "tie_break_rule": "task_id_then_start_minute",
            "limitations": [],
        },
        "warnings": [],
        "previous_schedule_hash": None,
        "revised_request_hash": None,
        "repaired_response_hash": None,
        "requires_human_acceptance": True,
        "accepted": False,
        "persistence_performed": False,
    }


def test_persisted_result_json_replays_strict_strategy_enum() -> None:
    result = PreparationScheduleRepairResult.model_validate(_result_document())

    assert result.diagnostics.strategy is PreparationRepairStrategy.GREEDY_MIN_CHANGE

    persisted = result.model_dump(mode="json")
    assert persisted["diagnostics"]["strategy"] == "greedy_min_change"
    assert PreparationScheduleRepairResult.model_validate(persisted) == result
