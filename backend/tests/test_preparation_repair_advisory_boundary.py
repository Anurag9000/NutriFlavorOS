from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair import (
    PreparationScheduleRepairRequest,
    PreparationScheduleRepairResult,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.engines.prep_schedule_repair import repair_preparation_schedule


def _repair_result() -> PreparationScheduleRepairResult:
    problem = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 60,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "person",
                    "capacity": 1,
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 60}
                    ],
                }
            ],
            "tasks": [
                {
                    "task_id": "prep",
                    "duration_minutes": 10,
                    "latest_finish_minute": 60,
                    "resource_demands": {"person": 1},
                }
            ],
        }
    )
    previous = build_preparation_schedule(problem)
    return repair_preparation_schedule(
        PreparationScheduleRepairRequest(
            previous_request=problem,
            previous_response=previous,
            revised_request=problem,
        )
    )


def test_repair_result_is_explicitly_advisory_and_non_persisted():
    result = _repair_result()

    assert result.requires_human_acceptance is True
    assert result.accepted is False
    assert result.persistence_performed is False


def test_repair_result_contract_rejects_implicit_acceptance_or_persistence():
    result = _repair_result()
    payload = result.model_dump(mode="python")

    for field in ("accepted", "persistence_performed"):
        contradictory = dict(payload)
        contradictory[field] = True
        with pytest.raises(ValidationError):
            PreparationScheduleRepairResult.model_validate(contradictory)

    contradictory = dict(payload)
    contradictory["requires_human_acceptance"] = False
    with pytest.raises(ValidationError):
        PreparationScheduleRepairResult.model_validate(contradictory)
