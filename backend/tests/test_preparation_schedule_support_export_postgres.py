from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

from sqlalchemy.orm import sessionmaker

from backend.domain.preparation_operations import PreparationScheduleEventType
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_operations_service import transition_schedule
from backend.services.preparation_repair_proposal_creation_service import (
    create_repair_proposal,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.services.preparation_schedule_support_export_service import (
    export_preparation_schedule_support_snapshot,
    preparation_schedule_support_evidence_hash,
)
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    transition_payload,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
)
from backend.tests.test_preparation_repair_proposals import proposal_payload


def _session_factory(db):
    assert db.get_bind().dialect.name == "postgresql", (
        "PostgreSQL support export probes must never run on SQLite"
    )
    return sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _export_worker(
    factory,
    schedule_id: int,
    snapshot_started: Event,
    continue_export: Event,
):
    session = factory()
    try:
        def pause_after_schedule_read(_):
            snapshot_started.set()
            assert continue_export.wait(timeout=20), (
                "support export race did not receive continuation signal"
            )

        return export_preparation_schedule_support_snapshot(
            session,
            household_id=HOUSEHOLD_ID,
            schedule_id=schedule_id,
            after_schedule_read=pause_after_schedule_read,
        )
    finally:
        session.close()


def test_postgres_support_export_is_repeatable_read_during_acceptance(db):
    factory = _session_factory(db)
    calendar = create_calendar(
        db,
        version="support-export-race-v1",
        key="support-export-race-calendar-v1",
    )
    draft = create_schedule(
        db,
        calendar,
        key="support-export-race-source-v1",
    )
    source = transition_schedule(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=draft.id,
        actor_user_id=OWNER_ID,
        event_type=PreparationScheduleEventType.APPROVED,
        payload=transition_payload(
            draft.version,
            "support-export-race-approve-v1",
            "Approve source before support export race",
        ),
    )
    proposal = create_repair_proposal(
        db,
        household_id=HOUSEHOLD_ID,
        actor_user_id=OWNER_ID,
        payload=proposal_payload(
            schedule=source,
            calendar=calendar,
            key="support-export-race-proposal-v1",
        ),
    )
    acceptance_request = acceptance_payload(
        proposal,
        key="support-export-race-acceptance-v1",
    )
    snapshot_started = Event()
    continue_export = Event()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            _export_worker,
            factory,
            source.id,
            snapshot_started,
            continue_export,
        )
        assert snapshot_started.wait(timeout=20), (
            "support export did not establish its snapshot"
        )
        acceptance_session = factory()
        try:
            accepted = accept_repair_proposal_with_source_guard(
                acceptance_session,
                household_id=HOUSEHOLD_ID,
                proposal_id=proposal.id,
                actor_user_id=OWNER_ID,
                payload=acceptance_request,
            )
        finally:
            acceptance_session.close()
            continue_export.set()
        historical = future.result(timeout=30)

    assert historical.database_dialect == "postgresql"
    assert historical.snapshot_isolation == "repeatable_read"
    assert historical.snapshot_read_only is True
    assert historical.snapshot_marker
    assert historical.schedule.id == source.id
    assert historical.schedule.status.value == "approved"
    assert historical.task_execution_eligibility.eligible is True
    assert historical.task_execution_eligibility.reason_code.value == "eligible"
    assert [
        value.status.value for value in historical.related_repair_proposals
    ] == ["proposed"]
    assert historical.repair_acceptances == []
    assert [
        value.event_type.value
        for value in historical.repair_proposal_events[str(proposal.id)]
    ] == ["created"]
    assert historical.evidence_hash == preparation_schedule_support_evidence_hash(
        historical
    )

    fresh_session = factory()
    try:
        current = export_preparation_schedule_support_snapshot(
            fresh_session,
            household_id=HOUSEHOLD_ID,
            schedule_id=source.id,
        )
    finally:
        fresh_session.close()

    assert current.snapshot_isolation == "repeatable_read"
    assert current.snapshot_read_only is True
    assert current.task_execution_eligibility.eligible is False
    assert (
        current.task_execution_eligibility.reason_code.value
        == "source_schedule_has_accepted_replacement"
    )
    assert (
        current.task_execution_eligibility.replacement_schedule_id
        == accepted.acceptance.created_schedule_id
    )
    assert [value.status.value for value in current.related_repair_proposals] == [
        "accepted"
    ]
    assert [value.id for value in current.repair_acceptances] == [
        accepted.acceptance.id
    ]
    assert [
        value.event_type.value
        for value in current.repair_proposal_events[str(proposal.id)]
    ] == ["created", "accepted"]
    assert current.evidence_hash == preparation_schedule_support_evidence_hash(
        current
    )
    assert current.evidence_hash != historical.evidence_hash

    db.expire_all()
    assert (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .count()
        == 1
    )
    assert (
        db.query(DBPersistedPreparationSchedule)
        .filter(
            DBPersistedPreparationSchedule.source_repair_proposal_id
            == proposal.id
        )
        .count()
        == 1
    )
    assert [
        value.event_type
        for value in (
            db.query(DBPreparationRepairProposalEvent)
            .filter(DBPreparationRepairProposalEvent.proposal_id == proposal.id)
            .order_by(DBPreparationRepairProposalEvent.id)
            .all()
        )
    ] == ["created", "accepted"]
