from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import preparation_operations_routes
from backend.database import Base, DBHousehold, DBUser, get_db
from backend.domain.household_access import HouseholdRole
from backend.domain.preparation import PreparationScheduleRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.utils.security import get_current_user


ROLE_RANK = {
    HouseholdRole.VIEWER: 1,
    HouseholdRole.EDITOR: 2,
    HouseholdRole.OWNER: 3,
}


def _client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        users = [
            DBUser(
                id=f"{role}@example.test",
                name=role.title(),
                liked_ingredients=[],
                disliked_ingredients=[],
                allergies=[],
                dietary_restrictions=[],
                health_conditions=[],
                medications=[],
            )
            for role in ("owner", "editor", "viewer", "outsider")
        ]
        household = DBHousehold(
            id="prep-home",
            owner_user_id="owner@example.test",
            name="Preparation home",
            timezone="UTC",
            version=1,
        )
        db.add_all([*users, household])
        db.commit()

    identity = {"user_id": "owner@example.test"}
    roles = {
        "owner@example.test": HouseholdRole.OWNER,
        "editor@example.test": HouseholdRole.EDITOR,
        "viewer@example.test": HouseholdRole.VIEWER,
    }

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def current_user():
        return SimpleNamespace(id=identity["user_id"])

    def access(db, household_id, user_id, minimum_role):
        if household_id != "prep-home" or user_id not in roles:
            raise HTTPException(status_code=404, detail="Resource not found")
        actual = roles[user_id]
        if ROLE_RANK[actual] < ROLE_RANK[minimum_role]:
            raise HTTPException(status_code=404, detail="Resource not found")
        return db.get(DBHousehold, household_id), SimpleNamespace(role=actual)

    monkeypatch.setattr(
        preparation_operations_routes,
        "require_household_access",
        access,
    )
    app = FastAPI()
    app.include_router(preparation_operations_routes.router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = current_user
    return TestClient(app), identity


def calendar_payload():
    return {
        "calendar_version": "reviewed-v1",
        "horizon_minutes": 120,
        "timezone": "UTC",
        "resources": [
            {
                "resource_id": "person",
                "label": "Available cook",
                "capacity": 1,
                "resource_kind": "person",
                "availability_windows": [
                    {"start_minute": 0, "end_minute": 30},
                    {"start_minute": 60, "end_minute": 120},
                ],
                "metadata": {},
            },
            {
                "resource_id": "burner",
                "label": "Burner",
                "capacity": 1,
                "resource_kind": "equipment",
                "availability_windows": [
                    {"start_minute": 0, "end_minute": 120}
                ],
                "metadata": {},
            },
        ],
        "evidence_status": "reviewed",
        "reviewed_at": "2026-08-01T00:00:00Z",
        "reviewed_by": "Calendar reviewer",
        "notes": "API fixture",
        "activate": True,
        "idempotency_key": "api-calendar-create-v1",
    }


def schedule_payload(calendar):
    request = PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": calendar["horizon_minutes"],
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": value["resource_id"],
                    "label": value["label"],
                    "capacity": value["capacity"],
                    "availability_windows": value["availability_windows"],
                }
                for value in calendar["resources"]
            ],
            "tasks": [
                {
                    "task_id": "prep",
                    "duration_minutes": 15,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 30,
                    "priority": 2,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {},
                },
                {
                    "task_id": "cook",
                    "duration_minutes": 20,
                    "earliest_start_minute": 60,
                    "latest_finish_minute": 120,
                    "priority": 1,
                    "resource_demands": {"person": 1, "burner": 1},
                    "dependencies": ["prep"],
                    "metadata": {},
                },
            ],
        }
    )
    response = build_preparation_schedule(request)
    return {
        "calendar_version_id": calendar["id"],
        "source_plan_id": None,
        "source_plan_version": None,
        "occurrence_set_version": "api-fixture-v1",
        "occurrence_set_hash": "a" * 64,
        "profile_versions": {},
        "schedule_request": request.model_dump(mode="json"),
        "schedule_response": response.model_dump(mode="json"),
        "notes": "API persisted schedule",
        "idempotency_key": "api-schedule-create-v1",
    }


def transition(version: int, key: str, reason: str):
    return {
        "expected_version": version,
        "reason": reason,
        "idempotency_key": key,
        "metadata": {"api_fixture": True},
    }


def test_role_aware_calendar_schedule_and_event_lifecycle(monkeypatch):
    client, identity = _client(monkeypatch)

    identity["user_id"] = "editor@example.test"
    denied = client.post(
        "/api/v1/households/prep-home/preparation-operations/resource-calendars",
        json=calendar_payload(),
    )
    assert denied.status_code == 404

    identity["user_id"] = "owner@example.test"
    created_calendar = client.post(
        "/api/v1/households/prep-home/preparation-operations/resource-calendars",
        json=calendar_payload(),
    )
    assert created_calendar.status_code == 200
    calendar = created_calendar.json()
    assert calendar["active"] is True
    assert calendar["evidence_status"] == "reviewed"
    assert len(calendar["resources"]) == 2

    identity["user_id"] = "editor@example.test"
    created_schedule = client.post(
        "/api/v1/households/prep-home/preparation-operations/schedules",
        json=schedule_payload(calendar),
    )
    assert created_schedule.status_code == 200
    schedule = created_schedule.json()
    assert schedule["status"] == "draft"
    assert schedule["version"] == 1

    identity["user_id"] = "viewer@example.test"
    listed = client.get(
        "/api/v1/households/prep-home/preparation-operations/schedules"
    )
    assert listed.status_code == 200
    assert [value["id"] for value in listed.json()] == [schedule["id"]]
    denied_approval = client.post(
        f"/api/v1/households/prep-home/preparation-operations/schedules/{schedule['id']}/approve",
        json=transition(1, "api-approve-v1", "Viewer cannot approve"),
    )
    assert denied_approval.status_code == 404

    identity["user_id"] = "owner@example.test"
    approved = client.post(
        f"/api/v1/households/prep-home/preparation-operations/schedules/{schedule['id']}/approve",
        json=transition(1, "api-approve-v1", "Owner reviewed schedule"),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["version"] == 2

    identity["user_id"] = "editor@example.test"
    completed = client.post(
        f"/api/v1/households/prep-home/preparation-operations/schedules/{schedule['id']}/complete",
        json=transition(2, "api-complete-v1", "Household confirmed completion"),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["version"] == 3

    identity["user_id"] = "viewer@example.test"
    events = client.get(
        f"/api/v1/households/prep-home/preparation-operations/schedules/{schedule['id']}/events"
    )
    assert events.status_code == 200
    assert [value["event_type"] for value in events.json()] == [
        "created",
        "approved",
        "completed",
    ]
    assert all(len(value["request_fingerprint"]) == 64 for value in events.json())


def test_outsider_and_cross_household_paths_do_not_disclose_resources(monkeypatch):
    client, identity = _client(monkeypatch)
    identity["user_id"] = "outsider@example.test"
    response = client.get(
        "/api/v1/households/prep-home/preparation-operations/resource-calendars"
    )
    assert response.status_code == 404

    identity["user_id"] = "owner@example.test"
    response = client.get(
        "/api/v1/households/other-home/preparation-operations/resource-calendars"
    )
    assert response.status_code == 404
