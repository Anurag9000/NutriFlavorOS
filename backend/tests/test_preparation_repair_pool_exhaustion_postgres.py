from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from backend.database_recovery_metrics import DATABASE_RECOVERY_METRICS
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


def test_postgres_pool_exhaustion_times_out_before_mutation_and_recovers(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "Pool exhaustion evidence must never run on SQLite"
    )
    _, _, proposal = create_proposal(db)
    idempotency_key = "pg-pool-exhaustion-exact-key"
    payload = acceptance_payload(proposal, key=idempotency_key)
    DATABASE_RECOVERY_METRICS.reset_for_tests()

    constrained_engine = create_engine(
        db.get_bind().url,
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.1,
        pool_pre_ping=True,
    )
    ConstrainedSession = sessionmaker(
        bind=constrained_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    holder = constrained_engine.connect()
    holder.execute(text("SELECT 1"))

    observations: list[DatabaseRetryObservation] = []
    delays: list[float] = []
    attempts: list[tuple[str, int]] = []
    zero_mutation_evidence: list[dict[str, int]] = []

    def observe(value: DatabaseRetryObservation) -> None:
        observations.append(value)
        zero_mutation_evidence.append(_accepted_counts(db, proposal.id))
        holder.close()

    def operation(exact_key: str, attempt: int):
        attempts.append((exact_key, attempt))
        assert exact_key == idempotency_key
        worker = ConstrainedSession()
        try:
            return accept_repair_proposal_with_source_guard(
                worker,
                household_id=HOUSEHOLD_ID,
                proposal_id=proposal.id,
                actor_user_id=OWNER_ID,
                payload=payload,
            )
        finally:
            worker.close()

    try:
        accepted = execute_exact_idempotent_database_request(
            operation,
            idempotency_key=idempotency_key,
            policy=ExactDatabaseRetryPolicy(
                max_attempts=2,
                base_delay_seconds=0,
                max_delay_seconds=0,
            ),
            observer=observe,
            sleep=delays.append,
        )

        assert attempts == [
            (idempotency_key, 1),
            (idempotency_key, 2),
        ]
        assert len(observations) == 1
        observation = observations[0]
        assert observation.code == "database_pool_timeout"
        assert observation.sqlstate is None
        assert observation.retry_safe is True
        assert observation.no_transaction_started is True
        assert observation.outcome_unknown is False
        assert observation.will_retry is True
        assert zero_mutation_evidence == [
            {
                "acceptances": 0,
                "replacement_schedules": 0,
                "proposal_accepted_events": 0,
                "replacement_created_events": 0,
            }
        ]
        assert delays == [0]

        retry_session = ConstrainedSession()
        try:
            replayed = accept_repair_proposal_with_source_guard(
                retry_session,
                household_id=HOUSEHOLD_ID,
                proposal_id=proposal.id,
                actor_user_id=OWNER_ID,
                payload=payload,
            )
        finally:
            retry_session.close()

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

        snapshot = DATABASE_RECOVERY_METRICS.snapshot()
        assert snapshot.code_counts == {"database_pool_timeout": 1}
        assert snapshot.retry_observation_total == 1
        assert snapshot.retry_scheduled_total == 1
        assert snapshot.retry_success_after_retry_total == 1
        assert snapshot.outcome_unknown_total == 0
    finally:
        if not holder.closed:
            holder.close()
        constrained_engine.dispose()
