from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from backend.database_recovery_metrics import DATABASE_RECOVERY_METRICS
from backend.exact_database_retry import (
    DatabaseRetryExhausted,
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


POOL_SIZE = 2
WORKERS_PER_WAVE = 8
PRESSURE_WAVES = 3
POOL_TIMEOUT_SECONDS = 0.12
EXPECTED_TIMEOUTS = WORKERS_PER_WAVE * PRESSURE_WAVES


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


def test_postgres_sustained_pool_pressure_times_out_cleanly_then_recovers(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "Sustained pool-pressure evidence must run on PostgreSQL"
    )
    _, _, proposal = create_proposal(db)
    idempotency_key = "pg-sustained-pool-pressure-exact-key"
    payload = acceptance_payload(proposal, key=idempotency_key)
    DATABASE_RECOVERY_METRICS.reset_for_tests()

    constrained_engine = create_engine(
        db.get_bind().url,
        poolclass=QueuePool,
        pool_size=POOL_SIZE,
        max_overflow=0,
        pool_timeout=POOL_TIMEOUT_SECONDS,
        pool_pre_ping=True,
    )
    ConstrainedSession = sessionmaker(
        bind=constrained_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    holders = [constrained_engine.connect() for _ in range(POOL_SIZE)]
    for holder in holders:
        holder.execute(text("SELECT 1"))
    assert constrained_engine.pool.checkedout() == POOL_SIZE

    zero_mutation_by_wave: list[dict[str, int]] = []
    timeout_observations: list[dict[str, object]] = []

    def run_one_pressure_attempt(barrier: Barrier, worker_number: int):
        barrier.wait(timeout=5)

        def operation(exact_key: str, attempt: int):
            assert exact_key == idempotency_key
            assert attempt == 1
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
            execute_exact_idempotent_database_request(
                operation,
                idempotency_key=idempotency_key,
                policy=ExactDatabaseRetryPolicy(
                    max_attempts=1,
                    base_delay_seconds=0,
                    max_delay_seconds=0,
                ),
                sleep=lambda _: None,
            )
        except DatabaseRetryExhausted as exc:
            assert len(exc.observations) == 1
            observation = exc.observations[0]
            return {
                "worker": worker_number,
                "code": observation.code,
                "retry_safe": observation.retry_safe,
                "no_transaction_started": observation.no_transaction_started,
                "outcome_unknown": observation.outcome_unknown,
                "will_retry": observation.will_retry,
                "attempt": observation.attempt,
            }
        raise AssertionError("occupied pool unexpectedly allowed a checkout")

    try:
        for wave in range(PRESSURE_WAVES):
            barrier = Barrier(WORKERS_PER_WAVE + 1)
            with ThreadPoolExecutor(max_workers=WORKERS_PER_WAVE) as executor:
                futures = [
                    executor.submit(
                        run_one_pressure_attempt,
                        barrier,
                        (wave * WORKERS_PER_WAVE) + worker,
                    )
                    for worker in range(WORKERS_PER_WAVE)
                ]
                barrier.wait(timeout=5)
                timeout_observations.extend(
                    future.result(timeout=10) for future in futures
                )

            db.expire_all()
            zero_mutation_by_wave.append(_accepted_counts(db, proposal.id))
            assert constrained_engine.pool.checkedout() == POOL_SIZE

        assert len(timeout_observations) == EXPECTED_TIMEOUTS
        assert [value["worker"] for value in timeout_observations] == list(
            range(EXPECTED_TIMEOUTS)
        )
        assert all(
            value
            == {
                "worker": index,
                "code": "database_pool_timeout",
                "retry_safe": True,
                "no_transaction_started": True,
                "outcome_unknown": False,
                "will_retry": False,
                "attempt": 1,
            }
            for index, value in enumerate(timeout_observations)
        )
        assert zero_mutation_by_wave == [
            {
                "acceptances": 0,
                "replacement_schedules": 0,
                "proposal_accepted_events": 0,
                "replacement_created_events": 0,
            }
            for _ in range(PRESSURE_WAVES)
        ]

        snapshot = DATABASE_RECOVERY_METRICS.snapshot()
        assert snapshot.code_counts == {
            "database_pool_timeout": EXPECTED_TIMEOUTS
        }
        assert snapshot.operational_error_total == 0
        assert snapshot.retry_observation_total == EXPECTED_TIMEOUTS
        assert snapshot.retry_scheduled_total == 0
        assert snapshot.retry_exhausted_total == EXPECTED_TIMEOUTS
        assert snapshot.outcome_unknown_total == 0
        assert snapshot.invalidated_connection_total == 0

        for holder in holders:
            holder.close()
        assert constrained_engine.pool.checkedout() == 0

        def recover(exact_key: str, attempt: int):
            assert exact_key == idempotency_key
            assert attempt == 1
            recovery_session = ConstrainedSession()
            try:
                return accept_repair_proposal_with_source_guard(
                    recovery_session,
                    household_id=HOUSEHOLD_ID,
                    proposal_id=proposal.id,
                    actor_user_id=OWNER_ID,
                    payload=payload,
                )
            finally:
                recovery_session.close()

        accepted = execute_exact_idempotent_database_request(
            recover,
            idempotency_key=idempotency_key,
            policy=ExactDatabaseRetryPolicy(
                max_attempts=1,
                base_delay_seconds=0,
                max_delay_seconds=0,
            ),
            sleep=lambda _: None,
        )

        replay_session = ConstrainedSession()
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

        with constrained_engine.connect() as health_connection:
            assert health_connection.execute(text("SELECT 1")).scalar_one() == 1
        assert constrained_engine.pool.checkedout() == 0
    finally:
        for holder in holders:
            if not holder.closed:
                holder.close()
        constrained_engine.dispose()
