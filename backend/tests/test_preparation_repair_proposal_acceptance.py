from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import HTTPException

from backend.database import DBHousehold, DBUser
from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    PreparationScheduleStatus,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
    PreparationRepairProposalStatus,
)
from backend.domain.preparation_schedule_replay import REPAIR_SCHEDULER_METHOD
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_operations_service import list_schedule_events
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
)
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_proposal_read_service import (
    get_repair_proposal,
    get_repair_proposal_acceptance,
    list_repair_proposal_events,
)
from backend.services.preparation_schedule_approval_service import (
    approve_schedule_authoritative,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    db,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload


def ensure_preparation_household(db) -> None:
    """Idempotently seed the shared household in externally managed databases.

    SQLite unit fixtures already create these rows. PostgreSQL recovery and
    failover suites own their database lifecycle, so imported proposal builders
    must establish the same authority fixture before invoking production
    household-locking services.
    """

    owner = db.get(DBUser, OWNER_ID)
    if owner is None:
        owner = DBUser(
            id=OWNER_ID,
            name="Owner",
            liked_ingredients=[],
            disliked_ingredients=[],
            allergies=[],
            dietary_restrictions=[],
            health_conditions=[],
            medications=[],
        )
        db.add(owner)
        db.flush()

    household = db.get(DBHousehold, HOUSEHOLD_ID)
    if household is None:
        db.add(
            DBHousehold(
                id=HOUSEHOLD_ID,
                owner_user_id=OWNER_ID,
                name="Preparation home",
                timezone="UTC",
                version=1,
            )
        )
        db.flush()
    elif household.owner_user_id != OWNER_ID:
        raise AssertionError("shared preparation household owner fixture drifted")


def create_proposal(db):
    ensure_preparation_household(db)
    calendar = create_calendar(db)
    source = create_schedule(db, calendar)
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(schedule=source, calendar=calendar),
    )
    return calendar, source, proposal


def acceptance_payload(
    proposal,
    *,
    key: str = "repair-acceptance-0001",
    acknowledgements: list[str] | None = None,
    proposal_version: int | None = None,
) -> PreparationRepairProposalAcceptRequest:
    return PreparationRepairProposalAcceptRequest.model_validate(
        {
            "expected_proposal_version": proposal_version or proposal.version,
            "expected_source_schedule_version": proposal.source_schedule_version,
            "expected_source_schedule_hash": proposal.source_schedule_hash,
            "expected_source_schedule_request_hash": (
                proposal.source_schedule_request_hash
            ),
            "expected_target_calendar_content_hash": (
                proposal.target_calendar_content_hash
            ),
            "expected_repair_request_hash": proposal.repair_request_hash,
            "expected_repair_result_hash": proposal.repair_result_hash,
            "expected_revised_request_hash": proposal.revised_request_hash,
            "expected_repaired_response_hash": proposal.repaired_response_hash,
            "acknowledged_task_ids": (
                proposal.required_acknowledgement_task_ids
                if acknowledgements is None
                else acknowledgements
            ),
            "reason": "Create a separately reviewable repaired draft",
            "acknowledge_creates_new_draft_only": True,
            "idempotency_key": key,
            "metadata": {"reviewed_change_count": 1},
        }
    )


def test_acceptance_creates_one_new_draft_and_preserves_source(db):
    calendar, source, proposal = create_proposal(db)
    source_before = db.get(DBPersistedPreparationSchedule, source.id)
    source_snapshot = {
        "status": source_before.status,
        "version": source_before.version,
        "schedule_hash": source_before.schedule_hash,
        "schedule_payload": deepcopy(source_before.schedule_payload),
    }

    accepted = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(proposal),
    )

    assert accepted.accepted is True
    assert accepted.schedule_persistence_performed is True
    assert accepted.approval_performed is False
    assert accepted.execution_performed is False
    assert accepted.proposal.status == PreparationRepairProposalStatus.ACCEPTED
    assert accepted.proposal.version == 2
    assert accepted.proposal.accepted_schedule_id == accepted.acceptance.created_schedule_id
    assert accepted.proposal.accepted_schedule_hash == accepted.acceptance.created_schedule_hash
    assert accepted.acceptance.created_schedule_status == "draft"
    assert accepted.acceptance.created_schedule_version == 1
    assert accepted.acceptance.derivation_method == REPAIR_SCHEDULER_METHOD
    assert accepted.acceptance.acknowledged_task_ids == ["dinner.prep"]

    source_after = db.get(DBPersistedPreparationSchedule, source.id)
    assert source_after.status == source_snapshot["status"]
    assert source_after.version == source_snapshot["version"]
    assert source_after.schedule_hash == source_snapshot["schedule_hash"]
    assert source_after.schedule_payload == source_snapshot["schedule_payload"]

    draft = db.get(
        DBPersistedPreparationSchedule,
        accepted.acceptance.created_schedule_id,
    )
    assert draft.id != source.id
    assert draft.status == PreparationScheduleStatus.DRAFT.value
    assert draft.version == 1
    assert draft.approved_by_user_id is None
    assert draft.approved_at is None
    assert draft.derivation_method == REPAIR_SCHEDULER_METHOD
    assert draft.source_repair_proposal_id == proposal.id
    assert draft.source_repair_proposal_version == 2
    assert draft.source_repair_request_hash == proposal.repair_request_hash
    assert draft.source_repair_result_hash == proposal.repair_result_hash
    assert draft.source_revised_request_hash == proposal.revised_request_hash
    assert draft.source_repaired_response_hash == proposal.repaired_response_hash
    assert draft.schedule_hash == accepted.acceptance.created_schedule_hash
    assert draft.calendar_version_id == calendar.id

    proposal_events = list_repair_proposal_events(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
    )
    assert [value.event_type.value for value in proposal_events] == [
        "created",
        "accepted",
    ]
    assert proposal_events[-1].metadata["created_schedule_id"] == draft.id
    assert proposal_events[-1].metadata["approval_performed"] is False
    assert proposal_events[-1].metadata["execution_performed"] is False

    schedule_events = list_schedule_events(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
    )
    assert [value.event_type for value in schedule_events] == [
        PreparationScheduleEventType.CREATED
    ]
    assert schedule_events[0].metadata["source_repair_proposal_id"] == proposal.id
    assert schedule_events[0].metadata["approval_performed"] is False


def test_acceptance_requires_exact_changed_task_acknowledgements(db):
    _, _, proposal = create_proposal(db)

    with pytest.raises(HTTPException) as missing:
        accept_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(proposal, acknowledgements=[]),
        )
    assert missing.value.status_code == 409
    assert missing.value.detail["code"] == "repair_acceptance_acknowledgement_mismatch"
    assert missing.value.detail["missing"] == ["dinner.prep"]

    with pytest.raises(HTTPException) as extra:
        accept_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(
                proposal,
                acknowledgements=["dinner.prep", "unexpected.task"],
                key="repair-acceptance-extra-ack",
            ),
        )
    assert extra.value.status_code == 409
    assert extra.value.detail["code"] == "repair_acceptance_acknowledgement_mismatch"
    assert extra.value.detail["unexpected"] == ["unexpected.task"]


def test_acceptance_is_exactly_idempotent_and_cross_key_repeat_fails(db):
    _, _, proposal = create_proposal(db)
    payload = acceptance_payload(proposal)

    first = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    retry = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    assert retry.acceptance.id == first.acceptance.id
    assert retry.acceptance.created_schedule_id == first.acceptance.created_schedule_id

    with pytest.raises(HTTPException) as different_key:
        accept_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(
                proposal,
                key="repair-acceptance-0002",
            ),
        )
    assert different_key.value.status_code == 409
    assert different_key.value.detail["code"] == "repair_proposal_already_accepted"

    contradictory = payload.model_copy(
        update={"reason": "Contradictory content under one acceptance key"}
    )
    with pytest.raises(HTTPException) as key_conflict:
        accept_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=contradictory,
        )
    assert key_conflict.value.status_code == 409
    assert key_conflict.value.detail["code"] == "repair_acceptance_idempotency_conflict"


def test_acceptance_rejects_stale_identity_before_persistence(db):
    _, _, proposal = create_proposal(db)
    wrong_hash = acceptance_payload(proposal).model_copy(
        update={"expected_repair_result_hash": "0" * 64}
    )

    with pytest.raises(HTTPException) as exc:
        accept_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=wrong_hash,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_acceptance_identity_mismatch"
    assert exc.value.detail["field"] == "repair_result_hash"
    assert (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .count()
        == 0
    )


def test_acceptance_rejects_source_execution_history(db):
    _, source, proposal = create_proposal(db)
    source_row = db.get(DBPersistedPreparationSchedule, source.id)
    source_row.version += 1
    db.add(source_row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        accept_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(proposal),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_acceptance_identity_mismatch"
    assert exc.value.detail["field"] == "live_source_schedule_version"


def test_repaired_draft_requires_method_aware_owner_approval(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(proposal),
    )
    draft_id = accepted.acceptance.created_schedule_id

    approved = approve_schedule_authoritative(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft_id,
        actor_user_id=OWNER_ID,
        payload=ScheduleStateTransitionRequest.model_validate(
            {
                "expected_version": 1,
                "reason": "Owner approved the separately reviewed repaired draft",
                "idempotency_key": "repair-draft-approval-0001",
                "metadata": {"reviewed_acceptance_id": accepted.acceptance.id},
            }
        ),
    )

    assert approved.status == PreparationScheduleStatus.APPROVED
    assert approved.version == 2
    events = list_schedule_events(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft_id,
    )
    assert [value.event_type.value for value in events] == ["created", "approved"]
    assert events[-1].metadata["method_aware_replay_verified"] is True
    assert events[-1].metadata["source_repair_proposal_id"] == proposal.id


def test_repaired_draft_approval_fails_after_proposal_hash_tamper(db):
    _, _, proposal = create_proposal(db)
    accepted = accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(proposal),
    )
    proposal_row = db.get(DBPreparationRepairProposal, proposal.id)
    proposal_row.repair_result_hash = "0" * 64
    db.add(proposal_row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        approve_schedule_authoritative(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=accepted.acceptance.created_schedule_id,
            actor_user_id=OWNER_ID,
            payload=ScheduleStateTransitionRequest.model_validate(
                {
                    "expected_version": 1,
                    "reason": "Attempt approval after tamper",
                    "idempotency_key": "repair-draft-approval-tamper",
                }
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_schedule_derivation_mismatch"
