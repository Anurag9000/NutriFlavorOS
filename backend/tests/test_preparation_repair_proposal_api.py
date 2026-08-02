from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import preparation_repair_proposal_routes
from backend.database import DBHouseholdMember, DBUser, get_db
from backend.services.preparation_repair_proposal_read_service import (
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


EDITOR_ID = "repair-editor@example.test"


def _client(
    db,
    *,
    authenticated: bool,
    user_id: str = OWNER_ID,
) -> TestClient:
    app = FastAPI()
    app.include_router(preparation_repair_proposal_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: db.get(
            DBUser,
            user_id,
        )
    return TestClient(app)


def _add_editor(db) -> None:
    editor = DBUser(
        id=EDITOR_ID,
        name="Repair Editor",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    membership = DBHouseholdMember(
        household_id=HOUSEHOLD_ID,
        display_name="Repair Editor",
        linked_user_id=EDITOR_ID,
        role="editor",
        servings_multiplier=1.0,
        allergies=[],
        dietary_restrictions=[],
        disliked_ingredients=[],
        active=True,
    )
    db.add_all([editor, membership])
    db.commit()


def _acceptance_payload(created: dict, *, key: str = "repair-api-accept-0001") -> dict:
    return {
        "expected_proposal_version": created["version"],
        "expected_source_schedule_version": created["source_schedule_version"],
        "expected_source_schedule_hash": created["source_schedule_hash"],
        "expected_source_schedule_request_hash": (
            created["source_schedule_request_hash"]
        ),
        "expected_target_calendar_content_hash": (
            created["target_calendar_content_hash"]
        ),
        "expected_repair_request_hash": created["repair_request_hash"],
        "expected_repair_result_hash": created["repair_result_hash"],
        "expected_revised_request_hash": created["revised_request_hash"],
        "expected_repaired_response_hash": created["repaired_response_hash"],
        "acknowledged_task_ids": created["required_acknowledgement_task_ids"],
        "reason": "Create a new draft after explicit repair review",
        "acknowledge_creates_new_draft_only": True,
        "idempotency_key": key,
        "metadata": {"api_review": True},
    }


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
    assert created["accepted_schedule_id"] is None
    assert created["accepted_schedule_hash"] is None
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


def test_editor_can_accept_into_draft_and_view_immutable_acceptance(db):
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

    accepted_response = client.post(
        f"{collection}/{created['id']}/accept",
        json=_acceptance_payload(created),
    )
    assert accepted_response.status_code == 200
    accepted = accepted_response.json()
    assert accepted["accepted"] is True
    assert accepted["schedule_persistence_performed"] is True
    assert accepted["approval_performed"] is False
    assert accepted["execution_performed"] is False
    assert accepted["proposal"]["status"] == "accepted"
    assert accepted["proposal"]["version"] == 2
    assert accepted["proposal"]["accepted"] is True
    assert accepted["proposal"]["schedule_persistence_performed"] is True
    assert accepted["acceptance"]["created_schedule_status"] == "draft"
    assert accepted["acceptance"]["created_schedule_version"] == 1
    assert len(accepted["acceptance"]["created_schedule_hash"]) == 64

    retry_response = client.post(
        f"{collection}/{created['id']}/accept",
        json=_acceptance_payload(created),
    )
    assert retry_response.status_code == 200
    assert (
        retry_response.json()["acceptance"]["id"]
        == accepted["acceptance"]["id"]
    )

    acceptance_response = client.get(
        f"{collection}/{created['id']}/acceptance"
    )
    assert acceptance_response.status_code == 200
    acceptance = acceptance_response.json()
    assert acceptance["id"] == accepted["acceptance"]["id"]
    assert acceptance["created_schedule_id"] == (
        accepted["acceptance"]["created_schedule_id"]
    )
    assert acceptance["created_schedule_status"] == "draft"

    events_response = client.get(f"{collection}/{created['id']}/events")
    assert events_response.status_code == 200
    assert [value["event_type"] for value in events_response.json()] == [
        "created",
        "accepted",
    ]


def test_acceptance_route_uses_source_version_uniqueness_guard(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    client = _client(db, authenticated=True)
    collection = (
        f"/api/v1/households/{HOUSEHOLD_ID}"
        "/preparation-operations/repair-proposals"
    )
    first_payload = proposal_payload(
        schedule=schedule,
        calendar=calendar,
        key="repair-api-source-guard-first",
    )
    second_payload = proposal_payload(
        schedule=schedule,
        calendar=calendar,
        key="repair-api-source-guard-second",
    )
    first = client.post(
        collection,
        json=first_payload.model_dump(mode="json"),
    ).json()
    second = client.post(
        collection,
        json=second_payload.model_dump(mode="json"),
    ).json()

    accepted = client.post(
        f"{collection}/{first['id']}/accept",
        json=_acceptance_payload(first, key="repair-api-source-guard-accept-first"),
    )
    assert accepted.status_code == 200

    conflict = client.post(
        f"{collection}/{second['id']}/accept",
        json=_acceptance_payload(second, key="repair-api-source-guard-accept-second"),
    )
    assert conflict.status_code == 409
    detail = conflict.json()["detail"]
    assert detail["code"] == "repair_source_already_has_accepted_replacement"
    assert detail["accepted_proposal_id"] == first["id"]
    assert detail["accepted_schedule_id"] == (
        accepted.json()["acceptance"]["created_schedule_id"]
    )


def test_acceptance_rejects_incomplete_acknowledgement(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    client = _client(db, authenticated=True)
    collection = (
        f"/api/v1/households/{HOUSEHOLD_ID}"
        "/preparation-operations/repair-proposals"
    )
    created = client.post(
        collection,
        json=proposal_payload(
            schedule=schedule,
            calendar=calendar,
        ).model_dump(mode="json"),
    ).json()
    payload = _acceptance_payload(created)
    payload["acknowledged_task_ids"] = []

    response = client.post(
        f"{collection}/{created['id']}/accept",
        json=payload,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "repair_acceptance_acknowledgement_mismatch"
    )


def test_owner_can_invalidate_but_editor_cannot(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    owner_client = _client(db, authenticated=True)
    collection = (
        f"/api/v1/households/{HOUSEHOLD_ID}"
        "/preparation-operations/repair-proposals"
    )
    created = owner_client.post(
        collection,
        json=proposal_payload(
            schedule=schedule,
            calendar=calendar,
            key="repair-api-invalidation-proposal",
        ).model_dump(mode="json"),
    ).json()
    payload = {
        "expected_version": created["version"],
        "reason": "Withdraw superseded review evidence",
        "acknowledge_historical_only": True,
        "idempotency_key": "repair-api-invalidation-owner",
        "metadata": {"admin_review": True},
    }

    _add_editor(db)
    editor_response = _client(
        db,
        authenticated=True,
        user_id=EDITOR_ID,
    ).post(
        f"{collection}/{created['id']}/invalidate",
        json=payload,
    )
    assert editor_response.status_code == 403

    invalidated_response = owner_client.post(
        f"{collection}/{created['id']}/invalidate",
        json=payload,
    )
    assert invalidated_response.status_code == 200
    invalidated = invalidated_response.json()
    assert invalidated["status"] == "invalidated"
    assert invalidated["version"] == 2
    assert invalidated["accepted"] is False
    assert invalidated["schedule_persistence_performed"] is False

    retry = owner_client.post(
        f"{collection}/{created['id']}/invalidate",
        json=payload,
    )
    assert retry.status_code == 200
    assert retry.json()["version"] == 2

    events = owner_client.get(f"{collection}/{created['id']}/events").json()
    assert [value["event_type"] for value in events] == [
        "created",
        "invalidated",
    ]
    assert events[-1]["metadata"]["historical_only"] is True


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
