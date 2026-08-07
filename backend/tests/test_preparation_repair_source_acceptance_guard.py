from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
    ScheduleStateTransitionRequest,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_execution_snapshot_service import (
    get_accepted_preparation_repair_task_lineage,
)
from backend.services.preparation_operations_service import transition_schedule
from backend.services.preparation_repair_proposal_acceptance_service import (
    accept_repair_proposal,
)
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
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


def _approved_source(db):
    calendar = create_calendar(db)
    source = create_schedule(db, calendar)
    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=ScheduleStateTransitionRequest.model_validate(
            {
                "expected_version": source.version,
                "reason": "Approve source before snapshot-bound repair test",
                "idempotency_key": "repair-source-snapshot-approve",
                "metadata": {"test": "snapshot-bound-repair"},
            }
        ),
    )
    return calendar, approved


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


def test_source_guard_rejects_execution_that_started_after_proposal_creation(db):
    calendar, source = _approved_source(db)
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(
            schedule=source,
            calendar=calendar,
            key="repair-source-snapshot-proposal",
        ),
    )
    task = source.schedule.scheduled[0]

    execution = record_task_execution_event(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
        task_id=task.task_id,
        actor_user_id=OWNER_ID,
        event_type=PreparationTaskExecutionEventType.STARTED,
        payload=PreparationTaskExecutionEventCreate.model_validate(
            {
                "expected_schedule_version": source.version,
                "actual_minute": task.start_minute,
                "reason": "Task started after repair proposal review snapshot",
                "notes": None,
                "idempotency_key": "repair-source-snapshot-task-start",
                "metadata": {"test": "snapshot-race"},
            }
        ),
    )

    with pytest.raises(HTTPException) as exc:
        accept_repair_proposal_with_source_guard(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(
                proposal,
                key="repair-source-snapshot-stale-acceptance",
            ),
        )

    assert execution.event.id > 0
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "repair_execution_snapshot_changed"
    assert exc.value.detail["observed_latest_execution_event_id"] == execution.event.id
    assert exc.value.detail["observed_execution_event_count"] == 1
    assert (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .count()
        == 0
    )


def test_task_lineage_requires_an_accepted_replacement(db):
    _, _, proposal = create_proposal(db)

    with pytest.raises(HTTPException) as exc:
        get_accepted_preparation_repair_task_lineage(
            db,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == (
        "repair_task_lineage_requires_accepted_replacement"
    )


def test_task_lineage_covers_every_source_and_replacement_task_after_acceptance(db):
    _, source, proposal = create_proposal(db)
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="repair-lineage-positive-acceptance",
        ),
    )

    lineage = get_accepted_preparation_repair_task_lineage(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
    )
    replacement = db.get(
        DBPersistedPreparationSchedule,
        accepted.acceptance.created_schedule_id,
    )
    assert replacement is not None

    source_task_ids = {value.task_id for value in source.schedule.scheduled}
    replacement_task_ids = {
        value["task_id"] for value in replacement.schedule_payload["scheduled"]
    }
    lineage_source_ids = {
        value.source_task_id for value in lineage.entries if value.source_task_id
    }
    lineage_replacement_ids = {
        value.replacement_task_id
        for value in lineage.entries
        if value.replacement_task_id
    }

    assert lineage.source_schedule_id == source.id
    assert lineage.source_schedule_version == proposal.source_schedule_version
    assert len(lineage.source_execution_snapshot_hash) == 64
    assert lineage_source_ids == source_task_ids
    assert lineage_replacement_ids == replacement_task_ids
    assert all(value.source_latest_event_id is None for value in lineage.entries)
    assert all(
        value.source_execution_state is None
        or value.source_execution_state.value == "planned"
        for value in lineage.entries
    )
    assert {
        value.status.value for value in lineage.entries
    } <= {
        "preserved",
        "shifted",
        "newly_introduced",
        "removed_before_execution",
        "superseded_by_replacement",
    }


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
