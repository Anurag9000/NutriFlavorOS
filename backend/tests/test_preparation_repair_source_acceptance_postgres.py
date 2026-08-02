from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
)
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    db,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL source acceptance races must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _accept_worker(factory, barrier: Barrier, proposal, key: str):
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
            "proposal_id": proposal.id,
            "acceptance_id": result.acceptance.id,
            "schedule_id": result.acceptance.created_schedule_id,
        }
    except HTTPException as exc:
        session.rollback()
        return {
            "kind": "conflict",
            "proposal_id": proposal.id,
            "status": exc.status_code,
            "code": (
                exc.detail.get("code")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
        }
    finally:
        session.close()


def test_postgres_competing_proposals_create_one_source_replacement(db):
    factory = _session_factory(db)
    calendar, schedule, first = create_proposal(db)
    second = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(
            schedule=schedule,
            calendar=calendar,
            key="pg-source-race-second-proposal",
        ),
    )
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _accept_worker,
                factory,
                barrier,
                first,
                "pg-source-race-first-acceptance",
            ),
            pool.submit(
                _accept_worker,
                factory,
                barrier,
                second,
                "pg-source-race-second-acceptance",
            ),
        ]
        results = [future.result(timeout=40) for future in futures]

    db.expire_all()
    acceptances = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(
            DBPreparationRepairProposalAcceptance.source_schedule_id
            == schedule.id,
            DBPreparationRepairProposalAcceptance.source_schedule_version
            == schedule.version,
        )
        .all()
    )
    schedules = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id.in_(
                [first.id, second.id]
            )
        )
        .all()
    )
    proposals = {
        value.id: value.status
        for value in (
            db.query(DBPreparationRepairProposal)
            .filter(DBPreparationRepairProposal.id.in_([first.id, second.id]))
            .all()
        )
    }

    assert len(acceptances) == 1
    assert len(schedules) == 1
    assert acceptances[0].created_schedule_id == schedules[0].id
    assert sum(value["kind"] == "accepted" for value in results) == 1
    assert sum(value["kind"] == "conflict" for value in results) == 1
    conflict = next(value for value in results if value["kind"] == "conflict")
    assert conflict["status"] == 409
    assert conflict["code"] in {
        "repair_source_already_has_accepted_replacement",
        "repair_acceptance_creation_conflict",
    }
    accepted_proposal_id = acceptances[0].proposal_id
    rejected_proposal_id = second.id if accepted_proposal_id == first.id else first.id
    assert proposals[accepted_proposal_id] == "accepted"
    assert proposals[rejected_proposal_id] == "proposed"
