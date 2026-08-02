from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import HTTPException

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalCreateRequest,
    PreparationRepairProposalRejectRequest,
    PreparationRepairProposalStatus,
)
from backend.preparation_repair_proposal_models import DBPreparationRepairProposal
from backend.services.preparation_operations_service import register_resource_calendar
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_proposal_read_service import (
    get_repair_proposal,
    list_repair_proposal_events,
    list_repair_proposals,
    reject_repair_proposal,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    calendar_payload,
    create_calendar,
    create_schedule,
    db,
    schedule_request,
)


def revised_request(calendar) -> PreparationScheduleRequest:
    payload = schedule_request(calendar).model_dump(mode="json")
    payload["tasks"][0]["earliest_start_minute"] = 5
    return PreparationScheduleRequest.model_validate(payload)


def proposal_payload(
    *,
    schedule,
    calendar,
    key: str = "repair-proposal-0001",
    expected_version: int | None = None,
    revised: PreparationScheduleRequest | None = None,
) -> PreparationRepairProposalCreateRequest:
    return PreparationRepairProposalCreateRequest.model_validate(
        {
            "source_schedule_id": schedule.id,
            "expected_source_version": expected_version or schedule.version,
            "target_calendar_version_id": calendar.id,
            "revised_request": (
                revised or revised_request(calendar)
            ).model_dump(mode="json"),
            "immutable_task_ids": [],
            "strategy": "greedy_min_change",
            "acknowledge_non_acceptance": True,
            "acknowledge_non_persistence": True,
            "notes": "Review the five-minute preparation shift",
            "idempotency_key": key,
        }
    )


def test_proposal_is_server_recomputed_hash_addressed_and_non_accepted(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)

    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(schedule=schedule, calendar=calendar),
    )

    assert proposal.status == PreparationRepairProposalStatus.PROPOSED
    assert proposal.version == 1
    assert proposal.current is True
    assert proposal.stale_reasons == []
    assert proposal.accepted is False
    assert proposal.schedule_persistence_performed is False
    assert proposal.accepted_schedule_id is None
    assert proposal.accepted_schedule_hash is None
    assert proposal.repair_result.requires_human_acceptance is True
    assert proposal.repair_result.accepted is False
    assert proposal.repair_result.persistence_performed is False
    assert proposal.repair_result.complete is True
    assert proposal.required_acknowledgement_task_ids == ["dinner.prep"]
    assert proposal.repair_result.moved_tasks[0].task_id == "dinner.prep"
    assert proposal.repair_result.moved_tasks[0].displacement_minutes == 5
    for value in [
        proposal.source_schedule_hash,
        proposal.source_schedule_request_hash,
        proposal.target_calendar_content_hash,
        proposal.repair_request_hash,
        proposal.repair_result_hash,
        proposal.revised_request_hash,
        proposal.repaired_response_hash,
    ]:
        assert len(value) == 64

    events = list_repair_proposal_events(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
    )
    assert len(events) == 1
    assert events[0].event_type.value == "created"
    assert events[0].proposal_version_before == 0
    assert events[0].proposal_version_after == 1
    assert events[0].metadata["accepted"] is False
    assert events[0].metadata["schedule_persistence_performed"] is False


def test_proposal_creation_is_exactly_idempotent_and_conflicting_reuse_fails(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    payload = proposal_payload(schedule=schedule, calendar=calendar)

    first = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    retry = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    assert retry.id == first.id
    assert retry.repair_result_hash == first.repair_result_hash

    contradictory = proposal_payload(
        schedule=schedule,
        calendar=calendar,
        revised=schedule_request(calendar),
    )
    with pytest.raises(HTTPException) as exc:
        create_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=contradictory,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_proposal_idempotency_conflict"


def test_distinct_request_keys_create_independent_review_records(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)

    first = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(schedule=schedule, calendar=calendar),
    )
    second_payload = proposal_payload(
        schedule=schedule,
        calendar=calendar,
        key="repair-proposal-0002",
    )
    second = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=second_payload,
    )

    assert second.id != first.id
    assert second.repair_result_hash == first.repair_result_hash
    assert len(list_repair_proposals(db, household_id=HOUSEHOLD_ID)) == 2

    contradictory = proposal_payload(
        schedule=schedule,
        calendar=calendar,
        key="repair-proposal-0002",
        revised=schedule_request(calendar),
    )
    with pytest.raises(HTTPException) as exc:
        create_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=contradictory,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_proposal_idempotency_conflict"


def test_creation_rejects_stale_source_version_and_provenance_drift(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)

    with pytest.raises(HTTPException) as exc:
        create_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=proposal_payload(
                schedule=schedule,
                calendar=calendar,
                expected_version=schedule.version + 1,
            ),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_source_version_mismatch"

    drifted = revised_request(calendar).model_dump(mode="json")
    drifted["tasks"][0]["metadata"]["servings"] = 3.0
    with pytest.raises(HTTPException) as exc:
        create_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            actor_user_id=OWNER_ID,
            payload=proposal_payload(
                schedule=schedule,
                calendar=calendar,
                key="repair-proposal-provenance-drift",
                revised=PreparationScheduleRequest.model_validate(drifted),
            ),
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "repair_proposal_provenance_mismatch"


def test_calendar_supersession_marks_proposal_stale_without_mutating_it(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(schedule=schedule, calendar=calendar),
    )

    replacement = register_resource_calendar(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=calendar_payload(
            "v2",
            "calendar-create-v2",
            second_window_start=65,
        ),
    )
    assert replacement.active is True

    stale = get_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
    )
    assert stale.status == PreparationRepairProposalStatus.PROPOSED
    assert stale.version == 1
    assert stale.current is False
    assert "target_calendar_not_active" in stale.stale_reasons
    assert "source_schedule_version_changed" in stale.stale_reasons
    assert "source_schedule_status_invalidated" in stale.stale_reasons
    assert stale.accepted is False
    assert stale.schedule_persistence_performed is False


def test_proposal_rejection_is_versioned_append_only_and_idempotent(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(schedule=schedule, calendar=calendar),
    )
    payload = PreparationRepairProposalRejectRequest.model_validate(
        {
            "expected_version": 1,
            "reason": "The movement is not acceptable for this household",
            "idempotency_key": "repair-proposal-reject-0001",
            "metadata": {"reviewed_change_count": 1},
        }
    )

    rejected = reject_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    retry = reject_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )

    assert retry.id == rejected.id
    assert rejected.status == PreparationRepairProposalStatus.REJECTED
    assert rejected.version == 2
    assert rejected.current is False
    assert rejected.rejection_reason == payload.reason
    assert rejected.accepted is False
    assert rejected.schedule_persistence_performed is False
    events = list_repair_proposal_events(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
    )
    assert [value.event_type.value for value in events] == ["created", "rejected"]
    assert events[-1].proposal_version_before == 1
    assert events[-1].proposal_version_after == 2

    contradictory = PreparationRepairProposalRejectRequest.model_validate(
        {
            **payload.model_dump(mode="json"),
            "reason": "A different reason under the same key",
        }
    )
    with pytest.raises(HTTPException) as exc:
        reject_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=contradictory,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_proposal_event_idempotency_conflict"


def test_proposal_read_fails_closed_after_payload_or_hash_tampering(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(schedule=schedule, calendar=calendar),
    )
    row = db.get(DBPreparationRepairProposal, proposal.id)
    tampered = deepcopy(row.repair_result_payload)
    tampered["accepted"] = True
    row.repair_result_payload = tampered
    db.add(row)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_proposal_payload_invalid"
