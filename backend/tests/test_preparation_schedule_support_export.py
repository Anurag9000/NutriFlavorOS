from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import preparation_operations_routes
from backend.database import DBUser, get_db
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.services.preparation_schedule_support_export_service import (
    export_preparation_schedule_support_snapshot,
    preparation_schedule_support_evidence_hash,
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
from scripts.export_preparation_schedule_support_snapshot import (
    build_export_payload,
    write_atomic_json,
)


def _row_counts(db) -> dict[str, int]:
    return {
        "schedules": db.query(DBPersistedPreparationSchedule).count(),
        "proposals": db.query(DBPreparationRepairProposal).count(),
        "acceptances": db.query(DBPreparationRepairProposalAcceptance).count(),
        "proposal_events": db.query(DBPreparationRepairProposalEvent).count(),
        "task_events": db.query(DBPreparationTaskExecutionEvent).count(),
    }


def _client(db, *, user_id: str | None) -> TestClient:
    app = FastAPI()
    app.include_router(preparation_operations_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    if user_id is not None:
        app.dependency_overrides[get_current_user] = lambda: db.get(
            DBUser,
            user_id,
        )
    return TestClient(app)


def test_original_schedule_export_is_hash_addressed_and_nonmutating(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    before = _row_counts(db)

    exported = export_preparation_schedule_support_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )

    assert exported.document_version == "preparation-schedule-support-export-v1"
    assert exported.database_dialect == "sqlite"
    assert exported.snapshot_isolation == "serializable"
    assert exported.snapshot_read_only is True
    assert exported.snapshot_marker is None
    assert exported.schedule.id == schedule.id
    assert exported.schedule.version == schedule.version
    assert exported.derivation.derivation_method.value == "original"
    assert exported.derivation.evidence_complete is True
    assert exported.task_execution_eligibility.eligible is False
    assert (
        exported.task_execution_eligibility.reason_code.value
        == "schedule_not_approved"
    )
    assert exported.task_execution.remaining_count == len(
        exported.task_execution.tasks
    )
    assert exported.related_repair_proposals == []
    assert exported.repair_acceptances == []
    assert exported.repair_proposal_events == {}
    assert exported.mutation_performed is False
    assert exported.actual_execution_verified is False
    assert exported.food_safety_verified is False
    assert exported.evidence_hash == preparation_schedule_support_evidence_hash(
        exported
    )
    assert _row_counts(db) == before


def test_source_and_replacement_exports_include_exact_repair_chain(db):
    _, source, proposal = create_proposal(db)
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="support-export-acceptance-v1",
        ),
    )
    replacement_id = accepted.acceptance.created_schedule_id
    before = _row_counts(db)

    source_export = export_preparation_schedule_support_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )
    replacement_export = export_preparation_schedule_support_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=replacement_id,
    )

    assert [value.id for value in source_export.related_repair_proposals] == [
        proposal.id
    ]
    assert [value.id for value in source_export.repair_acceptances] == [
        accepted.acceptance.id
    ]
    assert [
        value.event_type.value
        for value in source_export.repair_proposal_events[str(proposal.id)]
    ] == ["created", "accepted"]
    assert source_export.task_execution_eligibility.eligible is False
    assert (
        source_export.task_execution_eligibility.reason_code.value
        == "source_schedule_has_accepted_replacement"
    )
    assert (
        source_export.task_execution_eligibility.replacement_schedule_id
        == replacement_id
    )

    assert replacement_export.schedule.id == replacement_id
    assert replacement_export.derivation.derivation_method.value == "repair"
    assert replacement_export.derivation.source_repair_proposal_id == proposal.id
    assert (
        replacement_export.derivation.source_repair_acceptance_id
        == accepted.acceptance.id
    )
    assert [
        value.id for value in replacement_export.related_repair_proposals
    ] == [proposal.id]
    assert [value.id for value in replacement_export.repair_acceptances] == [
        accepted.acceptance.id
    ]
    assert replacement_export.evidence_hash == (
        preparation_schedule_support_evidence_hash(replacement_export)
    )
    assert source_export.evidence_hash != replacement_export.evidence_hash
    assert _row_counts(db) == before


def test_cli_helpers_render_and_atomically_replace_snapshot(db, tmp_path):
    calendar = create_calendar(
        db,
        version="support-cli-v1",
        key="support-cli-calendar-v1",
    )
    schedule = create_schedule(
        db,
        calendar,
        key="support-cli-schedule-v1",
    )
    output = tmp_path / "nested" / "support-export.json"
    output.parent.mkdir(parents=True)
    output.write_text('{"stale":true}\n', encoding="utf-8")
    before = _row_counts(db)

    payload = build_export_payload(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )
    write_atomic_json(output, payload)

    observed = json.loads(output.read_text(encoding="utf-8"))
    assert observed == payload
    assert observed["schedule_id"] == schedule.id
    assert observed["snapshot_read_only"] is True
    assert observed["mutation_performed"] is False
    assert not list(output.parent.glob(f".{output.name}.tmp-*"))
    assert _row_counts(db) == before


def test_support_export_endpoint_requires_authentication(db):
    calendar = create_calendar(
        db,
        version="support-api-auth-v1",
        key="support-api-auth-calendar-v1",
    )
    schedule = create_schedule(
        db,
        calendar,
        key="support-api-auth-schedule-v1",
    )

    response = _client(db, user_id=None).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        f"schedules/{schedule.id}/support-export"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_viewer_authorized_support_export_returns_read_only_evidence(db):
    calendar = create_calendar(
        db,
        version="support-api-owner-v1",
        key="support-api-owner-calendar-v1",
    )
    schedule = create_schedule(
        db,
        calendar,
        key="support-api-owner-schedule-v1",
    )
    before = _row_counts(db)

    response = _client(db, user_id=OWNER_ID).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        f"schedules/{schedule.id}/support-export"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_version"] == (
        "preparation-schedule-support-export-v1"
    )
    assert payload["household_id"] == HOUSEHOLD_ID
    assert payload["schedule_id"] == schedule.id
    assert payload["snapshot_read_only"] is True
    assert payload["mutation_performed"] is False
    assert len(payload["evidence_hash"]) == 64
    assert _row_counts(db) == before


def test_support_export_preserves_cross_household_non_disclosure(db):
    calendar = create_calendar(
        db,
        version="support-api-outsider-v1",
        key="support-api-outsider-calendar-v1",
    )
    schedule = create_schedule(
        db,
        calendar,
        key="support-api-outsider-schedule-v1",
    )
    outsider_id = "support-outsider@example.test"
    db.add(
        DBUser(
            id=outsider_id,
            name="Support outsider",
            liked_ingredients=[],
            disliked_ingredients=[],
            allergies=[],
            dietary_restrictions=[],
            health_conditions=[],
            medications=[],
        )
    )
    db.commit()

    response = _client(db, user_id=outsider_id).get(
        f"/api/v1/households/{HOUSEHOLD_ID}/preparation-operations/"
        f"schedules/{schedule.id}/support-export"
    )

    assert response.status_code == 404
