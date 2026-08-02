from __future__ import annotations

import json

from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.preparation_task_execution_models import (
    DBPreparationTaskExecutionEvent,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.services.preparation_schedule_support_export_service import (
    export_preparation_schedule_support_snapshot,
    preparation_schedule_support_evidence_hash,
)
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
    create_calendar,
    create_schedule,
    db,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)
from scripts.export_preparation_schedule_support_snapshot import (
    build_export_payload,
    write_atomic_json,
)


def _row_counts(db) -> dict[str, int]:
    return {
        "schedules": db.query(DBPersistedPreparationSchedule).count(),
        "proposals": db.query(DBPreparationRepairProposal).count(),
        "acceptances": db.query(DBPreparationRepairProposalAcceptance).count(),
        "proposal_events": db.query(DBPreparationRepairProposalEvent).count(),
        "task_events": db.query(DBPreparationTaskExecutionEvent).count(),
    }


def test_original_schedule_export_is_hash_addressed_and_nonmutating(db):
    calendar = create_calendar(db)
    schedule = create_schedule(db, calendar)
    before = _row_counts(db)

    exported = export_preparation_schedule_support_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )

    assert exported.document_version == "preparation-schedule-support-export-v1"
    assert exported.database_dialect == "sqlite"
    assert exported.snapshot_isolation == "serializable"
    assert exported.snapshot_read_only is True
    assert exported.snapshot_marker is None
    assert exported.schedule.id == schedule.id
    assert exported.schedule.version == schedule.version
    assert exported.derivation.derivation_method.value == "original"
    assert exported.derivation.evidence_complete is True
    assert exported.task_execution_eligibility.eligible is False
    assert (
        exported.task_execution_eligibility.reason_code.value
        == "schedule_not_approved"
    )
    assert exported.task_execution.remaining_count == len(
        exported.task_execution.tasks
    )
    assert exported.related_repair_proposals == []
    assert exported.repair_acceptances == []
    assert exported.repair_proposal_events == {}
    assert exported.mutation_performed is False
    assert exported.actual_execution_verified is False
    assert exported.food_safety_verified is False
    assert exported.evidence_hash == preparation_schedule_support_evidence_hash(
        exported
    )
    assert _row_counts(db) == before


def test_source_and_replacement_exports_include_exact_repair_chain(db):
    _, source, proposal = create_proposal(db)
    accepted = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=acceptance_payload(
            proposal,
            key="support-export-acceptance-v1",
        ),
    )
    replacement_id = accepted.acceptance.created_schedule_id
    before = _row_counts(db)

    source_export = export_preparation_schedule_support_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=source.id,
    )
    replacement_export = export_preparation_schedule_support_snapshot(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=replacement_id,
    )

    assert [value.id for value in source_export.related_repair_proposals] == [
        proposal.id
    ]
    assert [value.id for value in source_export.repair_acceptances] == [
        accepted.acceptance.id
    ]
    assert [
        value.event_type.value
        for value in source_export.repair_proposal_events[str(proposal.id)]
    ] == ["created", "accepted"]
    assert source_export.task_execution_eligibility.eligible is False
    assert (
        source_export.task_execution_eligibility.reason_code.value
        == "source_schedule_has_accepted_replacement"
    )
    assert (
        source_export.task_execution_eligibility.replacement_schedule_id
        == replacement_id
    )

    assert replacement_export.schedule.id == replacement_id
    assert replacement_export.derivation.derivation_method.value == "repair"
    assert replacement_export.derivation.source_repair_proposal_id == proposal.id
    assert (
        replacement_export.derivation.source_repair_acceptance_id
        == accepted.acceptance.id
    )
    assert [
        value.id for value in replacement_export.related_repair_proposals
    ] == [proposal.id]
    assert [value.id for value in replacement_export.repair_acceptances] == [
        accepted.acceptance.id
    ]
    assert replacement_export.evidence_hash == (
        preparation_schedule_support_evidence_hash(replacement_export)
    )
    assert source_export.evidence_hash != replacement_export.evidence_hash
    assert _row_counts(db) == before


def test_cli_helpers_render_and_atomically_replace_snapshot(db, tmp_path):
    calendar = create_calendar(
        db,
        version="support-cli-v1",
        key="support-cli-calendar-v1",
    )
    schedule = create_schedule(
        db,
        calendar,
        key="support-cli-schedule-v1",
    )
    output = tmp_path / "nested" / "support-export.json"
    output.parent.mkdir(parents=True)
    output.write_text('{"stale":true}\n', encoding="utf-8")
    before = _row_counts(db)

    payload = build_export_payload(
        db,
        household_id=HOUSEHOLD_ID,
        schedule_id=schedule.id,
    )
    write_atomic_json(output, payload)

    observed = json.loads(output.read_text(encoding="utf-8"))
    assert observed == payload
    assert observed["schedule_id"] == schedule.id
    assert observed["snapshot_read_only"] is True
    assert observed["mutation_performed"] is False
    assert not list(output.parent.glob(f".{output.name}.tmp-*"))
    assert _row_counts(db) == before
