from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalInvalidateRequest,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_repair_proposal_invalidation_service import (
    invalidate_repair_proposal,
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
        "PostgreSQL proposal invalidation races must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _accept_worker(factory, barrier: Barrier, proposal):
    session = factory()
    try:
        barrier.wait(timeout=20)
        result = accept_repair_proposal_with_source_guard(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=acceptance_payload(
                proposal,
                key="pg-repair-accept-versus-invalidate",
            ),
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


def _invalidate_worker(factory, barrier: Barrier, proposal):
    session = factory()
    try:
        barrier.wait(timeout=20)
        result = invalidate_repair_proposal(
            session,
            household_id=HOUSEHOLD_ID,
            proposal_id=proposal.id,
            actor_user_id=OWNER_ID,
            payload=PreparationRepairProposalInvalidateRequest.model_validate(
                {
                    "expected_version": proposal.version,
                    "reason": (
                        "Owner withdrew this proposal during the PostgreSQL race"
                    ),
                    "acknowledge_historical_only": True,
                    "idempotency_key": "pg-repair-invalidate-versus-accept",
                    "metadata": {"race_probe": True},
                }
            ),
        )
        return {"kind": "invalidated", "proposal_id": result.id}
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


def test_postgres_acceptance_racing_invalidation_has_one_terminal_outcome(db):
    factory = _session_factory(db)
    _, source, proposal = create_proposal(db)
    source_schedule_count = db.query(DBPersistedPreparationSchedule).count()
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        acceptance_future = pool.submit(
            _accept_worker,
            factory,
            barrier,
            proposal,
        )
        invalidation_future = pool.submit(
            _invalidate_worker,
            factory,
            barrier,
            proposal,
        )
        results = [
            acceptance_future.result(timeout=40),
            invalidation_future.result(timeout=40),
        ]

    db.expire_all()
    final = db.get(DBPreparationRepairProposal, proposal.id)
    assert final is not None
    acceptance_rows = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .all()
    )
    replacement_rows = (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id
            == proposal.id
        )
        .all()
    )
    event_types = [
        value.event_type
        for value in (
            db.query(DBPreparationRepairProposalEvent)
            .filter(DBPreparationRepairProposalEvent.proposal_id == proposal.id)
            .order_by(DBPreparationRepairProposalEvent.id)
            .all()
        )
    ]

    assert final.status in {"accepted", "invalidated"}
    assert sum(
        value["kind"] in {"accepted", "invalidated"}
        for value in results
    ) == 1
    assert sum(value["kind"] == "conflict" for value in results) == 1
    conflict = next(value for value in results if value["kind"] == "conflict")
    assert conflict["status"] == 409

    source_after = db.get(DBPersistedPreparationSchedule, source.id)
    assert source_after is not None
    assert source_after.id == source.id

    if final.status == "accepted":
        assert len(acceptance_rows) == 1
        assert len(replacement_rows) == 1
        assert acceptance_rows[0].created_schedule_id == replacement_rows[0].id
        assert db.query(DBPersistedPreparationSchedule).count() == (
            source_schedule_count + 1
        )
        assert event_types == ["created", "accepted"]
        assert conflict["code"] == "repair_proposal_not_invalidatable"
    else:
        assert acceptance_rows == []
        assert replacement_rows == []
        assert db.query(DBPersistedPreparationSchedule).count() == (
            source_schedule_count
        )
        assert event_types == ["created", "invalidated"]
        assert conflict["code"] in {
            "repair_proposal_not_acceptable",
            "repair_acceptance_identity_mismatch",
        }
