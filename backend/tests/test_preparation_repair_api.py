from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import preparation_routes
from backend.domain.preparation import PreparationScheduleRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.utils.security import get_current_user


def _client(*, authenticated: bool) -> TestClient:
    app = FastAPI()
    app.include_router(preparation_routes.router)
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="repairer@example.test"
        )
    return TestClient(app)


def _problem(*, duration_minutes: int = 10) -> dict:
    return {
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
                "duration_minutes": duration_minutes,
                "latest_finish_minute": 60,
                "resource_demands": {"person": 1},
            }
        ],
    }


def _payload(*, changed_immutable: bool = False) -> dict:
    previous = PreparationScheduleRequest.model_validate(_problem())
    response = build_preparation_schedule(previous)
    return {
        "previous_request": previous.model_dump(mode="json"),
        "previous_response": response.model_dump(mode="json"),
        "revised_request": _problem(
            duration_minutes=15 if changed_immutable else 10
        ),
        "immutable_task_ids": ["prep"] if changed_immutable else [],
        "strategy": "greedy_min_change",
        "allow_partial": False,
    }


def test_preparation_repair_requires_authentication():
    response = _client(authenticated=False).post(
        "/api/v1/preparation/schedule/repair",
        json=_payload(),
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_preparation_repair_is_advisory_and_non_persisting():
    response = _client(authenticated=True).post(
        "/api/v1/preparation/schedule/repair",
        json=_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["complete"] is True
    assert body["requires_human_acceptance"] is True
    assert body["accepted"] is False
    assert body["persistence_performed"] is False
    assert body["preserved_task_ids"] == ["prep"]
    assert body["moved_tasks"] == []


def test_preparation_repair_returns_structured_conflict():
    response = _client(authenticated=True).post(
        "/api/v1/preparation/schedule/repair",
        json=_payload(changed_immutable=True),
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "immutable_task_changed"
    assert detail["task_ids"] == ["prep"]
