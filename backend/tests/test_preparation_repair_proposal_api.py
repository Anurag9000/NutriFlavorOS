from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import preparation_repair_proposal_routes
from backend.database import DBUser, get_db
from backend.services.preparation_repair_proposal_service import (
    list_repair_proposals,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    db,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload
from backend.utils.security import get_current_user


def _client(db, *, authenticated: bool) -> TestClient:
    app = FastAPI()
    app.include_router(preparation_repair_proposal_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: db.get(
            DBUser,
            OWNER_ID,
        )
    return TestClient(app)


def test_repair_proposal_endpoints_require_authentication(db):
    response = _client(db, authenticated=False).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/repair-proposals"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_editor_can_create_read_list_and_reject_non_accepted_proposal(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    client = _client(db, authenticated=True)
    collection = (
        f"/api/v1/households/{HOUSEHOLD_ID}"
        "/preparation-operations/repair-proposals"
    )

    created_response = client.post(
        collection,
        json=proposal_payload(
            schedule=schedule,
            calendar=calendar,
        ).model_dump(mode="json"),
    )
    assert created_response.status_code == 200
    created = created_response.json()
    assert created["status"] == "proposed"
    assert created["accepted"] is False
    assert created["schedule_persistence_performed"] is False
    assert created["repair_result"]["accepted"] is False
    assert created["repair_result"]["persistence_performed"] is False

    retry_response = client.post(
        collection,
        json=proposal_payload(
            schedule=schedule,
            calendar=calendar,
        ).model_dump(mode="json"),
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["id"] == created["id"]

    listed_response = client.get(collection)
    assert listed_response.status_code == 200
    assert [value["id"] for value in listed_response.json()] == [created["id"]]

    read_response = client.get(f"{collection}/{created['id']}")
    assert read_response.status_code == 200
    assert read_response.json()["repair_result_hash"] == created["repair_result_hash"]

    events_response = client.get(f"{collection}/{created['id']}/events")
    assert events_response.status_code == 200
    assert [value["event_type"] for value in events_response.json()] == ["created"]

    rejected_response = client.post(
        f"{collection}/{created['id']}/reject",
        json={
            "expected_version": 1,
            "reason": "The proposed movement does not fit household availability",
            "idempotency_key": "repair-api-reject-0001",
            "metadata": {"reviewed": True},
        },
    )
    assert rejected_response.status_code == 200
    rejected = rejected_response.json()
    assert rejected["status"] == "rejected"
    assert rejected["version"] == 2
    assert rejected["accepted"] is False
    assert rejected["schedule_persistence_performed"] is False
    assert len(list_repair_proposals(db, household_id=HOUSEHOLD_ID)) == 1


def test_create_rejects_contradictory_idempotency_reuse(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    client = _client(db, authenticated=True)
    collection = (
        f"/api/v1/households/{HOUSEHOLD_ID}"
        "/preparation-operations/repair-proposals"
    )
    first_payload = proposal_payload(schedule=schedule, calendar=calendar)
    assert client.post(
        collection,
        json=first_payload.model_dump(mode="json"),
    ).status_code == 200

    contradictory = first_payload.model_dump(mode="json")
    contradictory["notes"] = "Contradictory content under the same key"
    response = client.post(collection, json=contradictory)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "repair_proposal_idempotency_conflict"
