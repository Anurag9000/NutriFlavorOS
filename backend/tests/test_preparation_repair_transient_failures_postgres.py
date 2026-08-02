from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from backend.preparation_operations_models import DBPersistedPreparationSchedule
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


DEADLOCK_ADVISORY_KEY = 9021001


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL transient-failure probes must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _sqlstate(exc: OperationalError) -> str | None:
    direct = getattr(exc.orig, "sqlstate", None)
    if isinstance(direct, str) and direct:
        return direct
    diagnostic = getattr(exc.orig, "diag", None)
    nested = getattr(diagnostic, "sqlstate", None)
    return nested if isinstance(nested, str) and nested else None


def _accept_with_statement_timeout(factory, proposal_id: int, payload):
    session = factory()
    try:
        session.execute(text("SET LOCAL statement_timeout = '150ms'"))
        accept_repair_proposal_with_source_guard(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
        return {"kind": "unexpected_acceptance"}
    except OperationalError as exc:
        state = _sqlstate(exc)
        session.rollback()
        return {"kind": "operational_error", "sqlstate": state}
    finally:
        session.close()


def _deadlock_accept_worker(
    factory,
    barrier: Barrier,
    proposal_id: int,
    payload,
):
    session = factory()
    try:
        session.execute(text("SET LOCAL deadlock_timeout = '100ms'"))
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": DEADLOCK_ADVISORY_KEY},
        )
        barrier.wait(timeout=20)
        result = accept_repair_proposal_with_source_guard(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
        return {
            "kind": "accepted",
            "acceptance_id": result.acceptance.id,
            "schedule_id": result.acceptance.created_schedule_id,
        }
    except OperationalError as exc:
        state = _sqlstate(exc)
        session.rollback()
        return {"kind": "operational_error", "sqlstate": state}
    finally:
        session.close()


def _deadlock_household_worker(factory, barrier: Barrier):
    session = factory()
    try:
        session.execute(text("SET LOCAL deadlock_timeout = '100ms'"))
        session.execute(
            text("SELECT id FROM households WHERE id = :household_id FOR UPDATE"),
            {"household_id": HOUSEHOLD_ID},
        )
        barrier.wait(timeout=20)
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": DEADLOCK_ADVISORY_KEY},
        )
        return {"kind": "helper_acquired"}
    except OperationalError as exc:
        state = _sqlstate(exc)
        session.rollback()
        return {"kind": "operational_error", "sqlstate": state}
    finally:
        session.rollback()
        session.close()


def _assert_one_accepted_replacement(db, proposal_id: int, accepted) -> None:
    db.expire_all()
    acceptances = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
        .all()
    )
    schedules = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id
            == proposal_id
        )
        .all()
    )
    event_types = [
        value.event_type
        for value in (
            db.query(DBPreparationRepairProposalEvent)
            .filter(DBPreparationRepairProposalEvent.proposal_id == proposal_id)
            .order_by(DBPreparationRepairProposalEvent.id)
            .all()
        )
    ]
    assert len(acceptances) == 1
    assert len(schedules) == 1
    assert acceptances[0].id == accepted.acceptance.id
    assert acceptances[0].created_schedule_id == accepted.acceptance.created_schedule_id
    assert schedules[0].id == accepted.acceptance.created_schedule_id
    assert event_types == ["created", "accepted"]


def test_postgres_statement_timeout_rolls_back_then_exact_retry_succeeds(db):
    factory = _session_factory(db)
    _, _, proposal = create_proposal(db)
    proposal_id = proposal.id
    payload = acceptance_payload(
        proposal,
        key="pg-statement-timeout-exact-retry",
    )

    blocker = factory()
    try:
        blocker.execute(
            text("SELECT id FROM households WHERE id = :household_id FOR UPDATE"),
            {"household_id": HOUSEHOLD_ID},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _accept_with_statement_timeout,
                factory,
                proposal_id,
                payload,
            )
            timed_out = future.result(timeout=20)
    finally:
        blocker.rollback()
        blocker.close()

    assert timed_out == {"kind": "operational_error", "sqlstate": "57014"}

    retry_session = factory()
    try:
        accepted = accept_repair_proposal_with_source_guard(
            retry_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    finally:
        retry_session.close()

    _assert_one_accepted_replacement(db, proposal_id, accepted)


def test_postgres_deadlock_victim_then_exact_retry_converges_once(db):
    factory = _session_factory(db)
    _, _, proposal = create_proposal(db)
    proposal_id = proposal.id
    payload = acceptance_payload(
        proposal,
        key="pg-deadlock-exact-retry",
    )
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        accept_future = pool.submit(
            _deadlock_accept_worker,
            factory,
            barrier,
            proposal_id,
            payload,
        )
        helper_future = pool.submit(
            _deadlock_household_worker,
            factory,
            barrier,
        )
        results = [
            accept_future.result(timeout=30),
            helper_future.result(timeout=30),
        ]

    deadlocks = [
        value
        for value in results
        if value.get("sqlstate") == "40P01"
    ]
    assert len(deadlocks) == 1
    assert sum(value["kind"] == "accepted" for value in results) in {0, 1}
    assert sum(value["kind"] == "helper_acquired" for value in results) in {0, 1}

    retry_session = factory()
    try:
        accepted = accept_repair_proposal_with_source_guard(
            retry_session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal_id,
            actor_user_id=OWNER_ID,
            payload=payload,
        )
    finally:
        retry_session.close()

    _assert_one_accepted_replacement(db, proposal_id, accepted)
