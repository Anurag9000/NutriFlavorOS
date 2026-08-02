from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalRejectRequest,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_repair_proposal_read_service import (
    reject_repair_proposal,
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
        "PostgreSQL repair acceptance probes must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _accept_worker(
    factory,
    barrier: Barrier,
    proposal,
    *,
    key: str,
):
    session = factory()
    try:
        barrier.wait(timeout=20)
        result = accept_repair_proposal_with_source_guard(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(proposal, key=key),
        )
        return {
            "kind": "accepted",
            "acceptance_id": result.acceptance.id,
            "schedule_id": result.acceptance.created_schedule_id,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "conflict",
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def _reject_worker(factory, barrier: Barrier, proposal):
    session = factory()
    try:
        barrier.wait(timeout=20)
        result = reject_repair_proposal(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=PreparationRepairProposalRejectRequest.model_validate(
                {
                    "expected_version": proposal.version,
                    "reason": "Competing PostgreSQL review rejected this repair",
                    "idempotency_key": "pg-repair-reject-race-0001",
                    "metadata": {"race_probe": True},
                }
            ),
        )
        return {"kind": "rejected", "proposal_id": result.id}
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "conflict",
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def _assert_single_acceptance_and_draft(db, proposal_id: int):
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
    assert len(acceptances) == 1
    assert len(schedules) == 1
    assert acceptances[0].created_schedule_id == schedules[0].id
    return acceptances[0], schedules[0]


def test_postgres_exact_duplicate_acceptance_returns_one_draft(db):
    factory = _session_factory(db)
    _, _, proposal = create_proposal(db)
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: _accept_worker(
                    factory,
                    barrier,
                    proposal,
                    key="pg-repair-accept-exact-duplicate",
                ),
                range(2),
            )
        )

    acceptance, schedule = _assert_single_acceptance_and_draft(db, proposal.id)
    accepted = [value for value in results if value["kind"] == "accepted"]
    assert len(accepted) == 2
    assert {value["acceptance_id"] for value in accepted} == {acceptance.id}
    assert {value["schedule_id"] for value in accepted} == {schedule.id}


def test_postgres_competing_acceptance_keys_create_only_one_draft(db):
    factory = _session_factory(db)
    _, _, proposal = create_proposal(db)
    barrier = Barrier(2)
    keys = ["pg-repair-accept-competing-a", "pg-repair-accept-competing-b"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _accept_worker,
                factory,
                barrier,
                proposal,
                key=key,
            )
            for key in keys
        ]
        results = [future.result(timeout=40) for future in futures]

    _assert_single_acceptance_and_draft(db, proposal.id)
    assert sum(value["kind"] == "accepted" for value in results) == 1
    conflicts = [value for value in results if value["kind"] == "conflict"]
    assert len(conflicts) == 1
    assert conflicts[0]["status"] == 409
    assert conflicts[0]["code"] in {
        "repair_proposal_already_accepted",
        "repair_acceptance_creation_conflict",
        "repair_proposal_not_acceptable",
        "repair_source_already_has_accepted_replacement",
    }


def test_postgres_acceptance_racing_rejection_has_one_terminal_outcome(db):
    factory = _session_factory(db)
    _, _, proposal = create_proposal(db)
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted_future = pool.submit(
            _accept_worker,
            factory,
            barrier,
            proposal,
            key="pg-repair-accept-versus-reject",
        )
        rejected_future = pool.submit(
            _reject_worker,
            factory,
            barrier,
            proposal,
        )
        results = [
            accepted_future.result(timeout=40),
            rejected_future.result(timeout=40),
        ]

    db.expire_all()
    final = db.get(DBPreparationRepairProposal, proposal.id)
    acceptance_count = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .count()
    )
    schedule_count = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id == proposal.id
        )
        .count()
    )
    assert final.status in {"accepted", "rejected"}
    assert sum(value["kind"] in {"accepted", "rejected"} for value in results) == 1
    assert sum(value["kind"] == "conflict" for value in results) == 1
    if final.status == "accepted":
        assert acceptance_count == 1
        assert schedule_count == 1
    else:
        assert acceptance_count == 0
        assert schedule_count == 0
