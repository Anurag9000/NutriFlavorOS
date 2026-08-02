from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import preparation_schedule_derivation_routes
from backend.database import DBUser, get_db
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
)
from backend.services.preparation_schedule_derivation_coverage_service import (
    get_schedule_derivation_coverage,
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


def test_empty_household_has_vacuous_complete_derivation_coverage(db):
    value = get_schedule_derivation_coverage(db, household_id=HOUSEHOLD_ID)

    assert value.schedule_total == 0
    assert value.original_schedule_count == 0
    assert value.repair_schedule_count == 0
    assert value.complete_derivation_count == 0
    assert value.incomplete_derivation_count == 0
    assert value.derivation_coverage_ratio == 1.0
    assert value.repair_acceptance_link_coverage_ratio == 1.0
    assert value.warnings == []


def test_original_schedule_counts_as_complete_without_repair_evidence(db):
    calendar = create_calendar(db)
    create_schedule(db, calendar)

    value = get_schedule_derivation_coverage(db, household_id=HOUSEHOLD_ID)

    assert value.schedule_total == 1
    assert value.original_schedule_count == 1
    assert value.repair_schedule_count == 0
    assert value.unknown_method_count == 0
    assert value.complete_derivation_count == 1
    assert value.incomplete_derivation_count == 0
    assert value.derivation_coverage_ratio == 1.0
    assert value.method_counts == {
        "deterministic_dependency_aware_resource_scheduler_v2": 1
    }


def test_accepted_repaired_draft_contributes_complete_acceptance_coverage(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-derivation-coverage-acceptance",
        ),
    )

    value = get_schedule_derivation_coverage(db, household_id=HOUSEHOLD_ID)

    assert value.schedule_total == 2
    assert value.original_schedule_count == 1
    assert value.repair_schedule_count == 1
    assert value.complete_derivation_count == 2
    assert value.incomplete_derivation_count == 0
    assert value.accepted_proposal_count == 1
    assert value.acceptance_record_count == 1
    assert value.repaired_draft_count == 1
    assert value.repaired_approved_count == 0
    assert value.repaired_execution_history_count == 0
    assert value.derivation_coverage_ratio == 1.0
    assert value.repair_acceptance_link_coverage_ratio == 1.0
    assert value.latest_acceptance_at == accepted.acceptance.created_at
    assert value.warnings == []


def test_tampered_acceptance_reduces_coverage_and_surfaces_warning(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-derivation-coverage-tamper",
        ),
    )
    row = db.get(DBPreparationRepairProposalAcceptance, accepted.acceptance.id)
    row.acknowledged_task_ids = []
    db.add(row)
    db.commit()

    value = get_schedule_derivation_coverage(db, household_id=HOUSEHOLD_ID)

    assert value.schedule_total == 2
    assert value.complete_derivation_count == 1
    assert value.incomplete_derivation_count == 1
    assert value.derivation_coverage_ratio == 0.5
    assert value.repair_acceptance_link_coverage_ratio == 0.0
    assert value.warnings == [
        f"schedule {accepted.acceptance.created_schedule_id} "
        "has incomplete repair derivation evidence"
    ]


def test_derivation_coverage_endpoint_requires_authentication(db):
    response = _client(db, authenticated=False).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        "schedule-derivation-coverage"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_viewer_authorized_coverage_endpoint_returns_denominators(db):
    calendar = create_calendar(db)
    create_schedule(db, calendar)
    response = _client(db, authenticated=True).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        "schedule-derivation-coverage"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schedule_total"] == 1
    assert payload["original_schedule_count"] == 1
    assert payload["derivation_coverage_ratio"] == 1.0
    assert payload["warnings"] == []
