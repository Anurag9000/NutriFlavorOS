from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import preparation_routes
from backend.utils.security import get_current_user


def _client(*, authenticated: bool) -> TestClient:
    app = FastAPI()
    app.include_router(preparation_routes.router)
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="scheduler@example.test"
        )
    return TestClient(app)


def test_preparation_schedule_requires_authentication():
    response = _client(authenticated=False).post(
        "/api/v1/preparation/schedule",
        json={
            "horizon_minutes": 60,
            "resources": [],
            "tasks": [],
        },
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_preparation_schedule_returns_capacity_diagnostics():
    response = _client(authenticated=True).post(
        "/api/v1/preparation/schedule",
        json={
            "horizon_minutes": 90,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "oven",
                    "capacity": 1,
                    "available_from_minute": 0,
                    "available_until_minute": 90,
                }
            ],
            "tasks": [
                {
                    "task_id": "bake-a",
                    "duration_minutes": 45,
                    "priority": 2,
                    "resource_demands": {"oven": 1},
                },
                {
                    "task_id": "bake-b",
                    "duration_minutes": 45,
                    "priority": 1,
                    "resource_demands": {"oven": 1},
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["deterministic"] is True
    assert [(task["task_id"], task["start_minute"]) for task in body["scheduled"]] == [
        ("bake-a", 0),
        ("bake-b", 45),
    ]
    assert body["unscheduled"] == []
    assert body["resource_peak_usage"] == {"oven": 1}
    assert body["resource_utilization"] == {"oven": 1.0}


def test_preparation_schedule_rejects_duplicate_resource_ids():
    response = _client(authenticated=True).post(
        "/api/v1/preparation/schedule",
        json={
            "horizon_minutes": 60,
            "resources": [
                {"resource_id": "oven", "capacity": 1},
                {"resource_id": "oven", "capacity": 2},
            ],
            "tasks": [],
        },
    )

    assert response.status_code == 422
    assert "resource_id values must be unique" in response.text
