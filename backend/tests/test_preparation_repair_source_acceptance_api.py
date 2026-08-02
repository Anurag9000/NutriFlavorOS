from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import preparation_repair_proposal_routes
from backend.database import DBUser, get_db
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    db,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload
from backend.utils.security import get_current_user


def _client(db) -> TestClient:
    app = FastAPI()
    app.include_router(preparation_repair_proposal_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(
        DBUser,
        OWNER_ID,
    )
    return TestClient(app)


def test_acceptance_endpoint_reports_existing_source_replacement(db):
    calendar, source, first = create_proposal(db)
    second = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(
            schedule=source,
            calendar=calendar,
            key="repair-source-api-second-proposal",
        ),
    )
    client = _client(db)
    root = (
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        "repair-proposals"
    )

    first_response = client.post(
        f"{root}/{first.id}/accept",
        json=acceptance_payload(
            first,
            key="repair-source-api-first-acceptance",
        ).model_dump(mode="json"),
    )
    assert first_response.status_code == 200
    accepted = first_response.json()

    second_response = client.post(
        f"{root}/{second.id}/accept",
        json=acceptance_payload(
            second,
            key="repair-source-api-second-acceptance",
        ).model_dump(mode="json"),
    )

    assert second_response.status_code == 409
    detail = second_response.json()["detail"]
    assert detail["code"] == "repair_source_already_has_accepted_replacement"
    assert detail["source_schedule_id"] == source.id
    assert detail["source_schedule_version"] == source.version
    assert detail["accepted_proposal_id"] == first.id
    assert detail["accepted_schedule_id"] == accepted["acceptance"][
        "created_schedule_id"
    ]
    assert detail["acceptance_id"] == accepted["acceptance"]["id"]
