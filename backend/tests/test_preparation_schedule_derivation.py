from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.api import preparation_schedule_derivation_routes
from backend.database import DBUser, get_db
from backend.domain.preparation_schedule_replay import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
    PreparationScheduleDerivationMethod,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
)
from backend.services.preparation_schedule_derivation_service import (
    get_schedule_derivation_evidence,
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
from backend.utils.security import get_current_user


def _client(db, *, authenticated: bool) -> TestClient:
    app = FastAPI()
    app.include_router(preparation_schedule_derivation_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: db.get(
            DBUser,
            OWNER_ID,
        )
    return TestClient(app)


def test_original_schedule_reports_original_method_and_no_repair_evidence(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)

    value = get_schedule_derivation_evidence(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )

    assert value.derivation_method == PreparationScheduleDerivationMethod.ORIGINAL
    assert value.derivation_method.value == ORIGINAL_SCHEDULER_METHOD
    assert value.evidence_complete is True
    assert value.schedule_id == schedule.id
    assert value.schedule_hash == schedule.schedule_hash
    assert value.source_repair_proposal_id is None
    assert value.source_repair_acceptance_id is None
    assert value.repair_request_hash is None
    assert value.accepted_by_user_id is None
    assert value.warnings == []


def test_accepted_repaired_draft_reports_complete_cross_record_evidence(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-derivation-evidence-acceptance",
        ),
    )

    value = get_schedule_derivation_evidence(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=accepted.acceptance.created_schedule_id,
    )

    assert value.derivation_method == PreparationScheduleDerivationMethod.REPAIR
    assert value.derivation_method.value == REPAIR_SCHEDULER_METHOD
    assert value.evidence_complete is True
    assert value.source_repair_proposal_id == proposal.id
    assert value.source_repair_proposal_version == 2
    assert value.source_repair_acceptance_id == accepted.acceptance.id
    assert value.source_schedule_id == proposal.source_schedule_id
    assert value.source_schedule_version == proposal.source_schedule_version
    assert value.repair_request_hash == proposal.repair_request_hash
    assert value.repair_result_hash == proposal.repair_result_hash
    assert value.revised_request_hash == proposal.revised_request_hash
    assert value.repaired_response_hash == proposal.repaired_response_hash
    assert value.accepted_by_user_id == OWNER_ID
    assert value.acceptance_reason == accepted.acceptance.reason
    assert value.warnings == []


def test_derivation_read_fails_closed_after_acceptance_tamper(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-derivation-tamper-acceptance",
        ),
    )
    row = db.get(DBPreparationRepairProposalAcceptance, accepted.acceptance.id)
    row.acknowledged_task_ids = []
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_schedule_derivation_evidence(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=accepted.acceptance.created_schedule_id,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "schedule_derivation_evidence_mismatch"
    assert exc.value.detail["field"] == "acknowledged_task_ids"


def test_derivation_service_preserves_household_non_disclosure(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)

    with pytest.raises(HTTPException) as exc:
        get_schedule_derivation_evidence(
            db,
            household_id="another-household",
            schedule_id=schedule.id,
        )

    assert exc.value.status_code == 404


def test_derivation_endpoint_requires_authentication(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    response = _client(db, authenticated=False).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        f"schedules/{schedule.id}/derivation"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_viewer_authorized_derivation_endpoint_returns_exact_evidence(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    response = _client(db, authenticated=True).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        f"schedules/{schedule.id}/derivation"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schedule_id"] == schedule.id
    assert payload["derivation_method"] == ORIGINAL_SCHEDULER_METHOD
    assert payload["evidence_complete"] is True
    assert payload["source_repair_proposal_id"] is None
