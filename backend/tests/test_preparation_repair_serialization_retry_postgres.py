from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.exact_database_retry import (
    DatabaseRetryObservation,
    ExactDatabaseRetryPolicy,
    execute_exact_idempotent_database_request,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


def _factory(db, *, serializable: bool = False):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL serialization retry evidence must never run on SQLite"
    )
    bind = db.get_bind()
    if serializable:
        bind = bind.execution_options(isolation_level="SERIALIZABLE")
    return sessionmaker(
        bind=bind,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _accepted_counts(db, proposal_id: int) -> dict[str, int]:
    return {
        "acceptances": (
            db.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .count()
        ),
        "replacement_schedules": (
            db.query(DBPersistedPreparationSchedule)
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == proposal_id
            )
            .count()
        ),
        "proposal_accepted_events": (
            db.query(DBPreparationRepairProposalEvent)
            .filter(
                DBPreparationRepairProposalEvent.proposal_id == proposal_id,
                DBPreparationRepairProposalEvent.event_type == "accepted",
            )
            .count()
        ),
        "replacement_created_events": (
            db.query(DBPreparationScheduleEvent)
            .join(
                DBPersistedPreparationSchedule,
                DBPersistedPreparationSchedule.id
                == DBPreparationScheduleEvent.schedule_id,
            )
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == proposal_id,
                DBPreparationScheduleEvent.event_type == "created",
            )
            .count()
        ),
    }


def test_postgres_repeated_serialization_failures_retry_exact_request_once(db):
    serial_factory = _factory(db, serializable=True)
    normal_factory = _factory(db)
    _, _, proposal = create_proposal(db)
    idempotency_key = "pg-bounded-serialization-retry"
    payload = acceptance_payload(proposal, key=idempotency_key)
    observations: list[DatabaseRetryObservation] = []
    delays: list[float] = []
    operation_attempts: list[tuple[str, int]] = []
    failed_attempts = 3

    def operation(exact_key: str, attempt: int):
        operation_attempts.append((exact_key, attempt))
        assert exact_key == payload.idempotency_key
        worker = serial_factory()
        try:
            observed_version = int(
                worker.execute(
                    text("SELECT version FROM households WHERE id = :household_id"),
                    {"household_id": HOUSEHOLD_ID},
                ).scalar_one()
            )
            if attempt <= failed_attempts:
                spoiler = normal_factory()
                try:
                    changed = spoiler.execute(
                        text(
                            "UPDATE households "
                            "SET version = version + 1, updated_at = NOW() "
                            "WHERE id = :household_id AND version = :observed_version"
                        ),
                        {
                            "household_id": HOUSEHOLD_ID,
                            "observed_version": observed_version,
                        },
                    )
                    assert changed.rowcount == 1
                    spoiler.commit()
                finally:
                    spoiler.close()
            return accept_repair_proposal_with_source_guard(
                worker,
                household_id=HOUSEHOLD_ID,
                proposal_id=proposal.id,
                actor_user_id=OWNER_ID,
                payload=payload,
            )
        finally:
            worker.close()

    accepted = execute_exact_idempotent_database_request(
        operation,
        idempotency_key=idempotency_key,
        policy=ExactDatabaseRetryPolicy(
            max_attempts=4,
            base_delay_seconds=0,
            max_delay_seconds=0,
        ),
        observer=observations.append,
        sleep=delays.append,
    )

    assert operation_attempts == [
        (idempotency_key, 1),
        (idempotency_key, 2),
        (idempotency_key, 3),
        (idempotency_key, 4),
    ]
    assert len(observations) == failed_attempts
    assert [value.sqlstate for value in observations] == [
        "40001",
        "40001",
        "40001",
    ]
    assert all(value.code == "database_transaction_retry_required" for value in observations)
    assert all(value.retryable is True for value in observations)
    assert all(value.retry_safe is True for value in observations)
    assert all(value.outcome_unknown is False for value in observations)
    assert all(value.will_retry is True for value in observations)
    assert delays == [0, 0, 0]

    replay_session = normal_factory()
    try:
        replayed = accept_repair_proposal_with_source_guard(
            replay_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    finally:
        replay_session.close()

    assert replayed.acceptance.id == accepted.acceptance.id
    assert replayed.acceptance.created_schedule_id == (
        accepted.acceptance.created_schedule_id
    )
    assert replayed.acceptance.idempotency_key == idempotency_key

    db.expire_all()
    assert _accepted_counts(db, proposal.id) == {
        "acceptances": 1,
        "replacement_schedules": 1,
        "proposal_accepted_events": 1,
        "replacement_created_events": 1,
    }
    proposal_events = (
        db.query(DBPreparationRepairProposalEvent)
        .filter(DBPreparationRepairProposalEvent.proposal_id == proposal.id)
        .order_by(DBPreparationRepairProposalEvent.id)
        .all()
    )
    assert [value.event_type for value in proposal_events] == [
        "created",
        "accepted",
    ]
