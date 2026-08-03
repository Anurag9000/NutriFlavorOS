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
        "PostgreSQL connection-loss recovery must never run on SQLite"
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


def test_postgres_connection_loss_after_commit_recovers_by_exact_retry(db):
    factory = _session_factory(db)
    _, _, proposal = create_proposal(db)
    payload = acceptance_payload(
        proposal,
        key="pg-post-commit-connection-loss-acceptance",
    )

    worker = factory()
    administrator = factory()
    worker_pid = int(
        worker.execute(text("SELECT pg_backend_pid()")).scalar_one()
    )
    original_refresh = worker.refresh
    termination_requested = False

    def terminate_before_first_refresh(instance, *args, **kwargs):
        nonlocal termination_requested
        if not termination_requested:
            termination_requested = True
            terminated = bool(
                administrator.execute(
                    text("SELECT pg_terminate_backend(:pid)"),
                    {"pid": worker_pid},
                ).scalar_one()
            )
            administrator.commit()
            assert terminated is True
        return original_refresh(instance, *args, **kwargs)

    worker.refresh = terminate_before_first_refresh  # type: ignore[method-assign]
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

    assert termination_requested is True
    assert observed_error is not None
    classification = classify_operational_error(observed_error)
    assert classification["code"] == "database_commit_outcome_unknown"
    assert classification["outcome_unknown"] is True
    assert classification["retry_safe"] is False
    assert classification["automatic_retry_performed"] is False

    db.expire_all()
    committed = _counts(db, proposal.id)
    assert committed == {
        "acceptances": 1,
        "replacement_schedules": 1,
        "proposal_accepted_events": 1,
        "replacement_created_events": 1,
    }
    committed_proposal = db.get(DBPreparationRepairProposal, proposal.id)
    assert committed_proposal is not None
    assert committed_proposal.status == "accepted"
    assert committed_proposal.version == proposal.version + 1

    retry_session = factory()
    try:
        recovered = accept_repair_proposal_with_source_guard(
            retry_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    finally:
        retry_session.close()

    assert recovered.accepted is True
    assert recovered.acceptance.proposal_id == proposal.id
    assert recovered.acceptance.idempotency_key == payload.idempotency_key
    assert recovered.acceptance.created_schedule_id == (
        recovered.proposal.accepted_schedule_id
    )

    db.expire_all()
    assert _counts(db, proposal.id) == committed
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
