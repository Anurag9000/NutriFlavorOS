from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleRequest,
)


def test_reviewed_windows_round_trip_without_legacy_defaults() -> None:
    resource = PreparationResource.model_validate(
        {
            "resource_id": "person",
            "capacity": 1,
            "availability_windows": [
                {"start_minute": 0, "end_minute": 60},
                {"start_minute": 90, "end_minute": 180},
            ],
            "label": "Available cook",
        }
    )

    document = resource.model_dump(mode="json")

    assert document["availability_windows"] == [
        {"start_minute": 0, "end_minute": 60},
        {"start_minute": 90, "end_minute": 180},
    ]
    assert "available_from_minute" not in document
    assert "available_until_minute" not in document
    assert PreparationResource.model_validate(document) == resource


def test_legacy_single_window_round_trip_without_empty_canonical_field() -> None:
    resource = PreparationResource.model_validate(
        {
            "resource_id": "burner",
            "capacity": 2,
            "available_from_minute": 15,
            "available_until_minute": 120,
        }
    )

    document = resource.model_dump(mode="json")

    assert document["available_from_minute"] == 15
    assert document["available_until_minute"] == 120
    assert "availability_windows" not in document
    assert PreparationResource.model_validate(document) == resource


def test_explicit_mixed_availability_representations_remain_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot be combined"):
        PreparationResource.model_validate(
            {
                "resource_id": "oven",
                "capacity": 1,
                "available_from_minute": 0,
                "available_until_minute": 120,
                "availability_windows": [
                    {"start_minute": 0, "end_minute": 120}
                ],
            }
        )


def test_nested_schedule_request_is_replayable_after_json_dump() -> None:
    request = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 180,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "person",
                    "capacity": 1,
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 180}
                    ],
                },
                {
                    "resource_id": "burner",
                    "capacity": 2,
                    "available_from_minute": 30,
                    "available_until_minute": 150,
                },
            ],
            "tasks": [],
        }
    )

    document = request.model_dump(mode="json")
    replay = PreparationScheduleRequest.model_validate(document)

    assert replay == request
    assert "available_from_minute" not in document["resources"][0]
    assert "availability_windows" not in document["resources"][1]
