from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import HTTPException

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalInvalidateRequest,
    PreparationRepairProposalRejectRequest,
    PreparationRepairProposalStatus,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.services.preparation_operations_service import register_resource_calendar
from backend.services.preparation_repair_proposal_invalidation_service import (
    invalidate_repair_proposal,
)
from backend.services.preparation_repair_proposal_read_service import (
    list_repair_proposal_events,
    reject_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    calendar_payload,
    db,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


def invalidation_payload(
    proposal,
    *,
    key: str = "repair-proposal-invalidate-0001",
    reason: str = "Withdraw this proposal from further acceptance review",
    version: int | None = None,
) -> PreparationRepairProposalInvalidateRequest:
    return PreparationRepairProposalInvalidateRequest.model_validate(
        {
            "expected_version": version or proposal.version,
            "reason": reason,
            "acknowledge_historical_only": True,
            "idempotency_key": key,
            "metadata": {"review_source": "owner_admin"},
        }
    )


def test_invalidation_is_append_only_historical_and_nonpersistent(db):
    _, source, proposal = create_proposal(db)
    before_count = db.query(DBPersistedPreparationSchedule).count()
    source_row = db.get(DBPersistedPreparationSchedule, source.id)
    source_snapshot = {
        "status": source_row.status,
        "version": source_row.version,
        "schedule_hash": source_row.schedule_hash,
        "schedule_payload": deepcopy(source_row.schedule_payload),
    }

    invalidated = invalidate_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=invalidation_payload(proposal),
    )

    assert invalidated.status == PreparationRepairProposalStatus.INVALIDATED
    assert invalidated.version == 2
    assert invalidated.current is False
    assert invalidated.accepted is False
    assert invalidated.schedule_persistence_performed is False
    assert invalidated.accepted_schedule_id is None
    assert invalidated.rejected_by_user_id is None
    assert invalidated.rejected_at is None
    assert invalidated.rejection_reason is None
    assert "proposal_status_invalidated" in invalidated.stale_reasons
    assert db.query(DBPersistedPreparationSchedule).count() == before_count

    source_after = db.get(DBPersistedPreparationSchedule, source.id)
    assert source_after.status == source_snapshot["status"]
    assert source_after.version == source_snapshot["version"]
    assert source_after.schedule_hash == source_snapshot["schedule_hash"]
    assert source_after.schedule_payload == source_snapshot["schedule_payload"]

    events = list_repair_proposal_events(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
    )
    assert [event.event_type.value for event in events] == [
        "created",
        "invalidated",
    ]
    invalidation = events[-1]
    assert invalidation.from_status == PreparationRepairProposalStatus.PROPOSED
    assert invalidation.to_status == PreparationRepairProposalStatus.INVALIDATED
    assert invalidation.proposal_version_before == 1
    assert invalidation.proposal_version_after == 2
    assert invalidation.metadata["historical_only"] is True
    assert invalidation.metadata["accepted"] is False
    assert invalidation.metadata["schedule_persistence_performed"] is False
    assert invalidation.metadata["approval_performed"] is False
    assert invalidation.metadata["execution_performed"] is False
    assert invalidation.metadata["observed_stale_reasons"] == []


def test_invalidation_captures_server_observed_stale_reasons(db):
    _, _, proposal = create_proposal(db)
    register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload(
            "replacement-v2",
            "repair-invalidation-calendar-v2",
            second_window_start=65,
        ),
    )

    invalidated = invalidate_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=invalidation_payload(
            proposal,
            key="repair-proposal-invalidate-stale",
            reason="Withdraw stale evidence after calendar supersession",
        ),
    )

    assert invalidated.status == PreparationRepairProposalStatus.INVALIDATED
    events = list_repair_proposal_events(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
    )
    observed = events[-1].metadata["observed_stale_reasons"]
    assert "target_calendar_not_active" in observed
    assert "source_schedule_version_changed" in observed
    assert "source_schedule_status_invalidated" in observed


def test_invalidation_is_exactly_idempotent_and_conflicting_reuse_fails(db):
    _, _, proposal = create_proposal(db)
    payload = invalidation_payload(proposal)

    first = invalidate_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    retry = invalidate_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    assert retry.id == first.id
    assert retry.version == 2

    contradictory = payload.model_copy(
        update={"reason": "Different withdrawal reason under the same key"}
    )
    with pytest.raises(HTTPException) as exc:
        invalidate_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=contradictory,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_proposal_event_idempotency_conflict"


def test_invalidation_rejects_stale_version_and_terminal_proposals(db):
    _, _, proposal = create_proposal(db)
    with pytest.raises(HTTPException) as stale:
        invalidate_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=invalidation_payload(
                proposal,
                version=proposal.version + 1,
                key="repair-proposal-invalidate-stale-version",
            ),
        )
    assert stale.value.detail["code"] == "repair_proposal_version_mismatch"

    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-invalidation-accept-first",
        ),
    )
    with pytest.raises(HTTPException) as accepted_error:
        invalidate_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=invalidation_payload(
                accepted.proposal,
                key="repair-invalidate-after-acceptance",
            ),
        )
    assert accepted_error.value.detail["code"] == "repair_proposal_not_invalidatable"
    assert accepted_error.value.detail["status"] == "accepted"


def test_rejection_prevents_later_invalidation(db):
    _, _, proposal = create_proposal(db)
    rejected = reject_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=PreparationRepairProposalRejectRequest.model_validate(
            {
                "expected_version": proposal.version,
                "reason": "Reject before invalidation attempt",
                "idempotency_key": "repair-rejection-before-invalidation",
                "metadata": {},
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        invalidate_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=invalidation_payload(
                rejected,
                key="repair-invalidate-after-rejection",
            ),
        )
    assert exc.value.detail["code"] == "repair_proposal_not_invalidatable"
    assert exc.value.detail["status"] == "rejected"
