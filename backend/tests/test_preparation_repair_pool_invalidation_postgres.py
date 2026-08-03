from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from backend.api.database_error_handlers import classify_operational_error
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
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


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL pool-invalidation recovery must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _counts(db, proposal_id: int) -> dict[str, int]:
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


def test_postgres_invalidated_checked_out_connection_recovers_on_fresh_session(db):
    factory = _session_factory(db)
    _, _, proposal = create_proposal(db)
    payload = acceptance_payload(
        proposal,
        key="pg-pool-invalidation-acceptance",
    )

    worker = factory()
    administrator = factory()
    dead_backend_pid = int(
        worker.execute(text("SELECT pg_backend_pid()")).scalar_one()
    )
    terminated = bool(
        administrator.execute(
            text("SELECT pg_terminate_backend(:pid)"),
            {"pid": dead_backend_pid},
        ).scalar_one()
    )
    administrator.commit()
    assert terminated is True

    observed_error: OperationalError | None = None
    try:
        accept_repair_proposal_with_source_guard(
            worker,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    except OperationalError as exc:
        observed_error = exc
    finally:
        worker.close()
        administrator.close()

    assert observed_error is not None
    assert observed_error.connection_invalidated is True
    classification = classify_operational_error(observed_error)
    assert classification["code"] == "database_commit_outcome_unknown"
    assert classification["outcome_unknown"] is True
    assert classification["retry_safe"] is False
    assert classification["automatic_retry_performed"] is False

    db.expire_all()
    assert _counts(db, proposal.id) == {
        "acceptances": 0,
        "replacement_schedules": 0,
        "proposal_accepted_events": 0,
        "replacement_created_events": 0,
    }
    unchanged = db.get(DBPreparationRepairProposal, proposal.id)
    assert unchanged is not None
    assert unchanged.status == "proposed"
    assert unchanged.version == proposal.version

    recovery_session = factory()
    try:
        recovery_backend_pid = int(
            recovery_session.execute(text("SELECT pg_backend_pid()")).scalar_one()
        )
        assert recovery_backend_pid != dead_backend_pid
        accepted = accept_repair_proposal_with_source_guard(
            recovery_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    finally:
        recovery_session.close()

    exact_retry_session = factory()
    try:
        replayed = accept_repair_proposal_with_source_guard(
            exact_retry_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    finally:
        exact_retry_session.close()

    assert replayed.acceptance.id == accepted.acceptance.id
    assert replayed.acceptance.created_schedule_id == (
        accepted.acceptance.created_schedule_id
    )
    assert replayed.acceptance.idempotency_key == payload.idempotency_key

    db.expire_all()
    assert _counts(db, proposal.id) == {
        "acceptances": 1,
        "replacement_schedules": 1,
        "proposal_accepted_events": 1,
        "replacement_created_events": 1,
    }
    events = (
        db.query(DBPreparationRepairProposalEvent)
        .filter(DBPreparationRepairProposalEvent.proposal_id == proposal.id)
        .order_by(DBPreparationRepairProposalEvent.id)
        .all()
    )
    assert [value.event_type for value in events] == ["created", "accepted"]
