from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from backend.domain.preparation_operations import (
    PreparationScheduleEventType,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalInvalidateRequest,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionEventCreate,
    PreparationTaskExecutionEventType,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_operations_service import transition_schedule
from backend.services.preparation_repair_proposal_invalidation_service import (
    invalidate_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.services.preparation_task_execution_service import (
    record_task_execution_event,
)
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    transition_payload,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL recovery probes must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _task_payload(
    *,
    version: int,
    minute: int,
    key: str,
) -> PreparationTaskExecutionEventCreate:
    return PreparationTaskExecutionEventCreate.model_validate(
        {
            "expected_schedule_version": version,
            "actual_minute": minute,
            "reason": None,
            "notes": "Prepare terminal schedule for recovery probe",
            "idempotency_key": key,
            "metadata": {"recovery_probe": True},
        }
    )


def test_postgres_acceptance_exact_retry_recovers_after_lost_response(db):
    factory = _session_factory(db)
    _, _, proposal = create_proposal(db)
    proposal_id = proposal.id
    payload = acceptance_payload(
        proposal,
        key="pg-recovery-acceptance-lost-response",
    )

    first_session = factory()
    try:
        # The service commits, but the caller deliberately discards the response.
        accept_repair_proposal_with_source_guard(
            first_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    finally:
        first_session.close()

    retry_session = factory()
    try:
        recovered = accept_repair_proposal_with_source_guard(
            retry_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
        recovered_acceptance_id = recovered.acceptance.id
        recovered_schedule_id = recovered.acceptance.created_schedule_id
    finally:
        retry_session.close()

    db.expire_all()
    acceptances = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
        .all()
    )
    drafts = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id
            == proposal_id
        )
        .all()
    )
    events = (
        db.query(DBPreparationRepairProposalEvent)
        .filter(DBPreparationRepairProposalEvent.proposal_id == proposal_id)
        .order_by(DBPreparationRepairProposalEvent.id)
        .all()
    )
    assert len(acceptances) == 1
    assert len(drafts) == 1
    assert acceptances[0].id == recovered_acceptance_id
    assert acceptances[0].created_schedule_id == recovered_schedule_id
    assert drafts[0].id == recovered_schedule_id
    assert [value.event_type for value in events] == ["created", "accepted"]


def test_postgres_invalidation_exact_retry_recovers_after_lost_response(db):
    factory = _session_factory(db)
    _, source, proposal = create_proposal(db)
    proposal_id = proposal.id
    source_id = source.id
    schedule_count = db.query(DBPersistedPreparationSchedule).count()
    payload = PreparationRepairProposalInvalidateRequest.model_validate(
        {
            "expected_version": proposal.version,
            "reason": "Withdraw proposal and recover after a lost response",
            "acknowledge_historical_only": True,
            "idempotency_key": "pg-recovery-invalidation-lost-response",
            "metadata": {"recovery_probe": True},
        }
    )

    first_session = factory()
    try:
        invalidate_repair_proposal(
            first_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    finally:
        first_session.close()

    retry_session = factory()
    try:
        recovered = invalidate_repair_proposal(
            retry_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
        assert recovered.status.value == "invalidated"
        assert recovered.version == proposal.version + 1
    finally:
        retry_session.close()

    db.expire_all()
    events = (
        db.query(DBPreparationRepairProposalEvent)
        .filter(DBPreparationRepairProposalEvent.proposal_id == proposal_id)
        .order_by(DBPreparationRepairProposalEvent.id)
        .all()
    )
    assert [value.event_type for value in events] == ["created", "invalidated"]
    assert db.query(DBPersistedPreparationSchedule).count() == schedule_count
    source_after = db.get(DBPersistedPreparationSchedule, source_id)
    assert source_after is not None
    assert source_after.status == source.status.value
    assert source_after.version == source.version


def test_postgres_completion_exact_retry_recovers_after_lost_response(db):
    factory = _session_factory(db)
    calendar = create_calendar(
        db,
        version="recovery-completion-v1",
        key="recovery-completion-calendar-v1",
    )
    draft = create_schedule(
        db,
        calendar,
        key="recovery-completion-schedule-v1",
    )
    approved = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            draft.version,
            "recovery-completion-approve-v1",
            "Approve schedule for recovery probe",
        ),
    )
    current_version = approved.version
    tasks = sorted(
        approved.schedule.scheduled,
        key=lambda value: (
            value.start_minute,
            value.finish_minute,
            value.task_id,
        ),
    )
    for index, task in enumerate(tasks):
        started = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.STARTED,
            payload=_task_payload(
                version=current_version,
                minute=task.start_minute,
                key=f"pg-recovery-task-start-{index}",
            ),
        )
        completed = record_task_execution_event(
            db,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            task_id=task.task_id,
            actor_user_id=OWNER_ID,
            event_type=PreparationTaskExecutionEventType.COMPLETED,
            payload=_task_payload(
                version=started.schedule.version,
                minute=task.finish_minute,
                key=f"pg-recovery-task-complete-{index}",
            ),
        )
        current_version = completed.schedule.version

    completion_payload = transition_payload(
        current_version,
        "pg-recovery-completion-lost-response",
        "Complete schedule and recover after a lost response",
    )
    first_session = factory()
    try:
        transition_schedule(
            first_session,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.COMPLETED,
            payload=completion_payload,
        )
    finally:
        first_session.close()

    retry_session = factory()
    try:
        recovered = transition_schedule(
            retry_session,
            household_id=HOUSEHOLD_ID,
            schedule_id=approved.id,
            actor_user_id=OWNER_ID,
            event_type=PreparationScheduleEventType.COMPLETED,
            payload=completion_payload,
        )
        assert recovered.status.value == "completed"
        assert recovered.version == current_version + 1
    finally:
        retry_session.close()

    db.expire_all()
    completed_events = (
        db.query(DBPreparationScheduleEvent)
        .filter(
            DBPreparationScheduleEvent.schedule_id == approved.id,
            DBPreparationScheduleEvent.event_type == "completed",
        )
        .all()
    )
    assert len(completed_events) == 1
    row = db.get(DBPersistedPreparationSchedule, approved.id)
    assert row is not None
    assert row.status == "completed"
    assert row.version == current_version + 1
