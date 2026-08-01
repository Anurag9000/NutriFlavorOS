from __future__ import annotations

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_operations_runtime import PersistedScheduleCreateRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule


PROFILE_HASH = "c" * 64


def verified_schedule_payload(
    *,
    household_id: str,
    calendar,
    idempotency_key: str,
    occurrence_id: str = "dinner",
    recipe_id: str = "recipe-a",
    servings: float = 2.0,
    priority: int = 3,
    required_finish_minute: int = 180,
) -> PersistedScheduleCreateRequest:
    request = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": calendar.horizon_minutes,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": resource.resource_id,
                    "label": resource.label,
                    "capacity": resource.capacity,
                    "availability_windows": [
                        window.model_dump(mode="json")
                        for window in resource.availability_windows
                    ],
                }
                for resource in calendar.resources
            ],
            "tasks": [
                {
                    "task_id": f"{occurrence_id}.prep",
                    "duration_minutes": 20,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": required_finish_minute,
                    "priority": priority,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {
                        "occurrence_id": occurrence_id,
                        "recipe_id": recipe_id,
                        "servings": servings,
                        "profile_id": 11,
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
    return PersistedScheduleCreateRequest.model_validate(
        {
            "calendar_version_id": calendar.id,
            "source_plan_id": None,
            "source_plan_version": None,
            "occurrence_set": {
                "document_version": "preparation-occurrence-set-v1",
                "household_id": household_id,
                "occurrence_set_version": "occurrences-v1",
                "duration_policy": "conservative_max",
                "occurrences": [
                    {
                        "occurrence_id": occurrence_id,
                        "recipe_id": recipe_id,
                        "required_finish_minute": required_finish_minute,
                        "servings": servings,
                        "priority": priority,
                    }
                ],
            },
            "profile_versions": {
                recipe_id: f"profile:11/version:v1/sha256:{PROFILE_HASH}"
            },
            "schedule_request": request.model_dump(mode="json"),
            "schedule_response": response.model_dump(mode="json"),
            "notes": "Reviewed deterministic schedule",
            "idempotency_key": idempotency_key,
        }
    )
