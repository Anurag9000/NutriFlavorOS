from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule


PROFILE_HASH = "a" * 64


def valid_payload() -> dict:
    request = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 180,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "person",
                    "label": "Available cook",
                    "capacity": 1,
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 180}
                    ],
                }
            ],
            "tasks": [
                {
                    "task_id": "dinner.prep",
                    "duration_minutes": 20,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 120,
                    "priority": 2,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {
                        "occurrence_id": "dinner",
                        "recipe_id": "recipe-a",
                        "servings": 2.0,
                        "profile_id": 1,
                        "profile_version": "v1",
                        "profile_content_hash": PROFILE_HASH,
                        "duration_min_minutes": 10,
                        "duration_max_minutes": 20,
                        "duration_policy": "conservative_max",
                        "template_id": "prep",
                        "active_work": True,
                        "unattended_allowed": False,
                    },
                }
            ],
        }
    )
    response = build_preparation_schedule(request)
    return {
        "calendar_version_id": 1,
        "occurrence_set": {
            "document_version": "preparation-occurrence-set-v1",
            "household_id": "home",
            "occurrence_set_version": "occurrences-v1",
            "duration_policy": "conservative_max",
            "occurrences": [
                {
                    "occurrence_id": "dinner",
                    "recipe_id": "recipe-a",
                    "required_finish_minute": 120,
                    "servings": 2.0,
                    "priority": 2,
                }
            ],
        },
        "profile_versions": {
            "recipe-a": f"profile:1/version:v1/sha256:{PROFILE_HASH}"
        },
        "schedule_request": request.model_dump(mode="json"),
        "schedule_response": response.model_dump(mode="json"),
        "idempotency_key": "occurrence-contract-v1",
    }


def test_verified_occurrence_contract_accepts_exact_provenance():
    value = PersistedScheduleCreateRequest.model_validate(valid_payload())
    assert value.occurrence_set_version == "occurrences-v1"
    assert len(value.occurrence_set_hash) == 64


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["occurrence_set"]["occurrences"][0].update(recipe_id="other"), "recipe_id"),
        (lambda value: value["occurrence_set"]["occurrences"][0].update(servings=3.0), "servings"),
        (lambda value: value["occurrence_set"]["occurrences"][0].update(priority=9), "priority"),
        (lambda value: value["occurrence_set"]["occurrences"][0].update(required_finish_minute=130), "deadline"),
        (lambda value: value["schedule_request"]["tasks"][0]["metadata"].update(duration_max_minutes=25), "duration"),
        (lambda value: value["profile_versions"].update({"recipe-a": f"profile:1/version:v1/sha256:{'b' * 64}"}), "profile_versions hashes"),
    ],
)
def test_occurrence_contract_rejects_task_provenance_drift(mutation, message):
    payload = deepcopy(valid_payload())
    mutation(payload)
    with pytest.raises(ValidationError, match=message):
        PersistedScheduleCreateRequest.model_validate(payload)


def test_occurrence_contract_rejects_uncompiled_occurrence():
    payload = valid_payload()
    payload["occurrence_set"]["occurrences"].append(
        {
            "occurrence_id": "lunch",
            "recipe_id": "recipe-a",
            "required_finish_minute": 90,
            "servings": 2.0,
            "priority": 1,
        }
    )
    with pytest.raises(ValidationError, match="without compiled tasks"):
        PersistedScheduleCreateRequest.model_validate(payload)
