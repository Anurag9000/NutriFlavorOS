from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
)
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
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


def _second_proposal(db, *, calendar, schedule, key: str):
    return create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(
            schedule=schedule,
            calendar=calendar,
            key=key,
        ),
    )


def test_source_guard_preserves_exact_retry_for_same_proposal(db):
    _, _, proposal = create_proposal(db)
    payload = acceptance_payload(
        proposal,
        key="repair-source-guard-exact-retry",
    )

    first = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    retry = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )

    assert retry.acceptance.id == first.acceptance.id
    assert retry.acceptance.created_schedule_id == (
        first.acceptance.created_schedule_id
    )


def test_source_guard_rejects_second_proposal_for_same_source_version(db):
    calendar, schedule, first_proposal = create_proposal(db)
    second_proposal = _second_proposal(
        db,
        calendar=calendar,
        schedule=schedule,
        key="repair-source-guard-second-proposal",
    )
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=first_proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            first_proposal,
            key="repair-source-guard-first-acceptance",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        accept_repair_proposal_with_source_guard(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=second_proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(
                second_proposal,
                key="repair-source-guard-second-acceptance",
            ),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == (
        "repair_source_already_has_accepted_replacement"
    )
    assert exc.value.detail["source_schedule_id"] == schedule.id
    assert exc.value.detail["source_schedule_version"] == schedule.version
    assert exc.value.detail["accepted_proposal_id"] == first_proposal.id
    assert exc.value.detail["accepted_schedule_id"] == (
        accepted.acceptance.created_schedule_id
    )
    assert exc.value.detail["acceptance_id"] == accepted.acceptance.id

    assert (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.source_schedule_id
            == schedule.id,
            DBPreparationRepairProposalAcceptance.source_schedule_version
            == schedule.version,
        )
        .count()
        == 1
    )
    assert (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id.in_(
                [first_proposal.id, second_proposal.id]
            )
        )
        .count()
        == 1
    )


def test_database_constraint_blocks_direct_service_bypass(db):
    calendar, schedule, first_proposal = create_proposal(db)
    second_proposal = _second_proposal(
        db,
        calendar=calendar,
        schedule=schedule,
        key="repair-source-constraint-second-proposal",
    )
    accept_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=first_proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            first_proposal,
            key="repair-source-constraint-first-acceptance",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        accept_repair_proposal(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=second_proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(
                second_proposal,
                key="repair-source-constraint-second-acceptance",
            ),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] in {
        "repair_acceptance_creation_conflict",
        "repair_source_already_has_accepted_replacement",
    }
    assert (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.source_schedule_id
            == schedule.id,
            DBPreparationRepairProposalAcceptance.source_schedule_version
            == schedule.version,
        )
        .count()
        == 1
    )
