from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

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
from backend.tests.postgres_commit_ack_drop_proxy import (
    PostgresCommitAckDropProxy,
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


ZERO_COUNTS = {
    "acceptances": 0,
    "replacement_schedules": 0,
    "proposal_accepted_events": 0,
    "replacement_created_events": 0,
}
ONE_COUNTS = {
    "acceptances": 1,
    "replacement_schedules": 1,
    "proposal_accepted_events": 1,
    "replacement_created_events": 1,
}


def _accepted_counts(db, proposal_id: int) -> dict[str, int]:
    db.rollback()
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


def _proxy_database_url(db, proxy_port: int):
    direct_url = db.get_bind().url
    query = dict(direct_url.query)
    query.update(
        {
            "connect_timeout": "5",
            "gssencmode": "disable",
            "sslmode": "disable",
        }
    )
    return direct_url.set(
        host="127.0.0.1",
        port=proxy_port,
        query=query,
    )


def test_postgres_commit_acknowledgement_loss_recovers_exact_committed_request(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "COMMIT acknowledgement loss evidence must run on PostgreSQL"
    )
    _, _, proposal = create_proposal(db)
    idempotency_key = "pg-commit-ack-loss-exact-key"
    payload = acceptance_payload(proposal, key=idempotency_key)
    assert _accepted_counts(db, proposal.id) == ZERO_COUNTS

    direct_url = db.get_bind().url
    upstream_host = direct_url.host or "127.0.0.1"
    upstream_port = int(direct_url.port or 5432)
    captured_error: OperationalError | None = None

    proxy = PostgresCommitAckDropProxy(
        upstream_host=upstream_host,
        upstream_port=upstream_port,
    )
    with proxy:
        proxy.wait_until_ready()
        proxied_engine = create_engine(
            _proxy_database_url(db, proxy.listen_port),
            poolclass=NullPool,
            pool_pre_ping=False,
        )
        ProxiedSession = sessionmaker(
            bind=proxied_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        worker = ProxiedSession()
        try:
            worker.execute(text("SET LOCAL synchronous_commit = on"))
            assert worker.execute(text("SHOW synchronous_commit")).scalar_one() == "on"
            with pytest.raises(OperationalError) as caught:
                accept_repair_proposal_with_source_guard(
                    worker,
                    household_id=HOUSEHOLD_ID,
                    proposal_id=proposal.id,
                    actor_user_id=OWNER_ID,
                    payload=payload,
                )
            captured_error = caught.value
            proxy.wait_for_commit_ack_drop()
        finally:
            worker.close()
            proxied_engine.dispose()

    assert captured_error is not None
    classification = classify_operational_error(captured_error)
    assert classification["code"] == "database_commit_outcome_unknown"
    assert classification["retryable"] is True
    assert classification["retry_safe"] is False
    assert classification["transaction_aborted"] is False
    assert classification["outcome_unknown"] is True
    assert classification["retry_same_idempotency_key"] is True
    assert classification["automatic_retry_performed"] is False
    assert captured_error.connection_invalidated is True

    proxy_report = proxy.report()
    assert proxy_report.commit_query_seen is True
    assert proxy_report.commit_query_forwarded is True
    assert proxy_report.commit_command_complete_seen is True
    assert proxy_report.commit_acknowledgement_forwarded is False
    assert proxy_report.client_connection_closed_after_drop is True
    assert proxy_report.upstream_connection_closed_after_drop is True
    assert proxy_report.proxy_threads_stopped is True

    # PostgreSQL generated CommandComplete(COMMIT) with synchronous_commit=on,
    # so an independent direct connection must see the committed lifecycle even
    # though the caller never received that acknowledgement and raised an
    # outcome-unknown error.
    assert _accepted_counts(db, proposal.id) == ONE_COUNTS
    proposal_row = db.get(DBPreparationRepairProposal, proposal.id)
    assert proposal_row is not None
    db.refresh(proposal_row)
    assert proposal_row.status == "accepted"

    acceptance = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .one()
    )
    accepted_schedule_id = int(acceptance.created_schedule_id)
    accepted_schedule = db.get(DBPersistedPreparationSchedule, accepted_schedule_id)
    assert accepted_schedule is not None
    assert accepted_schedule.status == "draft"
    assert accepted_schedule.version == 1

    replayed = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    assert replayed.acceptance.id == acceptance.id
    assert replayed.acceptance.created_schedule_id == accepted_schedule_id
    assert replayed.acceptance.idempotency_key == idempotency_key
    assert _accepted_counts(db, proposal.id) == ONE_COUNTS

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
