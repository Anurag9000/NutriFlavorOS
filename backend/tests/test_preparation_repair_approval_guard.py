from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.domain.preparation_operations import (
    PreparationScheduleStatus,
    ScheduleStateTransitionRequest,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_repair_approval_guard_service import (
    approve_schedule_with_repair_acceptance_guard,
)
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
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


def _accepted_draft(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-approval-guard-acceptance",
        ),
    )
    return proposal, accepted


def _approval_payload(key: str) -> ScheduleStateTransitionRequest:
    return ScheduleStateTransitionRequest.model_validate(
        {
            "expected_version": 1,
            "reason": "Owner approved after exact acceptance and replay review",
            "idempotency_key": key,
            "metadata": {"guard_test": True},
        }
    )


def test_guard_allows_exact_repaired_draft_owner_approval(db):
    proposal, accepted = _accepted_draft(db)

    approved = approve_schedule_with_repair_acceptance_guard(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=accepted.acceptance.created_schedule_id,
        actor_user_id=OWNER_ID,
        payload=_approval_payload("repair-approval-guard-success"),
    )

    assert approved.status == PreparationScheduleStatus.APPROVED
    assert approved.version == 2
    assert accepted.proposal.id == proposal.id


def test_guard_rejects_tampered_acknowledgement_set(db):
    _, accepted = _accepted_draft(db)
    row = db.get(DBPreparationRepairProposalAcceptance, accepted.acceptance.id)
    row.acknowledged_task_ids = []
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        approve_schedule_with_repair_acceptance_guard(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=accepted.acceptance.created_schedule_id,
            actor_user_id=OWNER_ID,
            payload=_approval_payload("repair-approval-guard-bad-ack"),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_approval_acceptance_mismatch"
    assert exc.value.detail["field"] == "acknowledged_task_ids"


def test_guard_rejects_tampered_acceptance_hash(db):
    _, accepted = _accepted_draft(db)
    row = db.get(DBPreparationRepairProposalAcceptance, accepted.acceptance.id)
    row.repair_result_hash = "0" * 64
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        approve_schedule_with_repair_acceptance_guard(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=accepted.acceptance.created_schedule_id,
            actor_user_id=OWNER_ID,
            payload=_approval_payload("repair-approval-guard-bad-hash"),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_approval_acceptance_mismatch"
    assert exc.value.detail["field"] == "acceptance_repair_result_hash"


def test_guard_rejects_tampered_source_identity(db):
    _, accepted = _accepted_draft(db)
    row = db.get(DBPreparationRepairProposalAcceptance, accepted.acceptance.id)
    row.source_schedule_version += 1
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        approve_schedule_with_repair_acceptance_guard(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=accepted.acceptance.created_schedule_id,
            actor_user_id=OWNER_ID,
            payload=_approval_payload("repair-approval-guard-bad-source"),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_approval_acceptance_mismatch"
    assert exc.value.detail["field"] == "source_schedule_version"
