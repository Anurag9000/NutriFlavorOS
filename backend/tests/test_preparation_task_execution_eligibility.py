from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import preparation_task_execution_eligibility_routes
from backend.database import DBUser, get_db
from backend.domain.preparation_operations import ScheduleStateTransitionRequest
from backend.services.preparation_repair_approval_guard_service import (
    approve_schedule_with_repair_acceptance_guard,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.services.preparation_task_execution_eligibility_service import (
    get_task_execution_eligibility,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    db,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)
from backend.tests.test_preparation_task_execution_service import (
    create_approved_schedule,
)
from backend.utils.security import get_current_user


def _client(db, *, authenticated: bool) -> TestClient:
    app = FastAPI()
    app.include_router(preparation_task_execution_eligibility_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: db.get(
            DBUser,
            OWNER_ID,
        )
    return TestClient(app)


def test_approved_schedule_without_replacement_is_execution_eligible(db):
    schedule = create_approved_schedule(db)

    value = get_task_execution_eligibility(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )

    assert value.eligible is True
    assert value.reason_code.value == "eligible"
    assert value.schedule_status == "approved"
    assert value.task_event_count == 0
    assert value.accepted_proposal_id is None
    assert value.replacement_schedule_id is None


def test_draft_schedule_is_not_execution_eligible(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)

    value = get_task_execution_eligibility(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )

    assert value.eligible is False
    assert value.reason_code.value == "schedule_not_approved"
    assert value.schedule_status == "draft"
    assert value.accepted_proposal_id is None


def test_source_schedule_reports_exact_accepted_replacement_block(db):
    _, source, proposal = create_proposal(db)
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-execution-eligibility-acceptance",
        ),
    )

    value = get_task_execution_eligibility(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )

    assert value.eligible is False
    assert value.reason_code.value == "source_schedule_has_accepted_replacement"
    assert value.accepted_proposal_id == proposal.id
    assert value.acceptance_id == accepted.acceptance.id
    assert value.replacement_schedule_id == accepted.acceptance.created_schedule_id
    assert value.replacement_schedule_status == "draft"
    assert value.replacement_schedule_version == 1


def test_replacement_becomes_eligible_only_after_owner_approval(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-execution-eligibility-replacement",
        ),
    )
    replacement_id = accepted.acceptance.created_schedule_id

    draft = get_task_execution_eligibility(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=replacement_id,
    )
    assert draft.eligible is False
    assert draft.reason_code.value == "schedule_not_approved"

    approve_schedule_with_repair_acceptance_guard(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=replacement_id,
        actor_user_id=OWNER_ID,
        payload=ScheduleStateTransitionRequest.model_validate(
            {
                "expected_version": 1,
                "reason": "Approve replacement for explicit task execution",
                "idempotency_key": "repair-execution-eligibility-approval",
            }
        ),
    )
    approved = get_task_execution_eligibility(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=replacement_id,
    )
    assert approved.eligible is True
    assert approved.reason_code.value == "eligible"
    assert approved.schedule_status == "approved"


def test_task_execution_eligibility_endpoint_requires_authentication(db):
    schedule = create_approved_schedule(db)
    response = _client(db, authenticated=False).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        f"schedules/{schedule.id}/task-execution-eligibility"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_viewer_authorized_eligibility_endpoint_returns_reason(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    response = _client(db, authenticated=True).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        f"schedules/{schedule.id}/task-execution-eligibility"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schedule_id"] == schedule.id
    assert payload["eligible"] is False
    assert payload["reason_code"] == "schedule_not_approved"
