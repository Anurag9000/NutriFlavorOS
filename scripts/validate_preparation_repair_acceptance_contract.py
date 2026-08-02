#!/usr/bin/env python3
"""Validate accepted repair draft persistence and method-aware approval."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from backend.database import Base
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalEventType,
    PreparationRepairProposalStatus,
)
from backend.preparation_operations_models import DBPersistedPreparationSchedule
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposalAcceptance,
)
from backend.schema_revision import CURRENT_ALEMBIC_REVISION
from backend.schema_verification import CURRENT_REQUIRED_TABLES


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "domain": "backend/domain/preparation_repair_proposals.py",
    "replay_domain": "backend/domain/preparation_schedule_replay.py",
    "acceptance_model": "backend/preparation_repair_proposal_models.py",
    "schedule_model": "backend/preparation_operations_models.py",
    "migration": "backend/migrations/versions/20260802_0017_repair_proposal_acceptance.py",
    "acceptance_service": "backend/services/preparation_repair_proposal_acceptance_service.py",
    "approval_service": "backend/services/preparation_schedule_approval_service.py",
    "proposal_routes": "backend/api/preparation_repair_proposal_routes.py",
    "schedule_routes": "backend/api/preparation_operations_routes.py",
    "tests": "backend/tests/test_preparation_repair_proposal_acceptance.py",
    "api_tests": "backend/tests/test_preparation_repair_proposal_api.py",
    "docs": "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing acceptance file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _require(
    source: str,
    fragments: set[str],
    label: str,
    errors: list[str],
) -> None:
    for fragment in sorted(fragments):
        if fragment not in source:
            errors.append(f"{label} lacks required fragment: {fragment}")


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    if CURRENT_ALEMBIC_REVISION != "20260802_0017":
        errors.append("runtime migration head must be 20260802_0017")
    if "preparation_repair_proposal_acceptances" not in CURRENT_REQUIRED_TABLES:
        errors.append("runtime schema does not require acceptance table")
    for table in [
        "preparation_repair_proposal_acceptances",
        "preparation_repair_proposals",
        "persisted_preparation_schedules",
    ]:
        if table not in Base.metadata.tables:
            errors.append(f"ORM metadata lacks acceptance table dependency: {table}")

    statuses = {value.value for value in PreparationRepairProposalStatus}
    if statuses != {"proposed", "accepted", "rejected", "invalidated"}:
        errors.append(f"proposal statuses drifted: {sorted(statuses)}")
    events = {value.value for value in PreparationRepairProposalEventType}
    if events != {"created", "accepted", "rejected", "invalidated"}:
        errors.append(f"proposal events drifted: {sorted(events)}")

    acceptance_table = DBPreparationRepairProposalAcceptance.__table__
    unique_constraints = {
        value.name: tuple(column.name for column in value.columns)
        for value in acceptance_table.constraints
        if isinstance(value, UniqueConstraint)
    }
    expected_uniques = {
        "uq_preparation_repair_acceptance_proposal": ("proposal_id",),
        "uq_preparation_repair_acceptance_schedule": ("created_schedule_id",),
        "uq_preparation_repair_acceptance_household_idempotency": (
            "household_id",
            "idempotency_key",
        ),
    }
    for name, columns in expected_uniques.items():
        if unique_constraints.get(name) != columns:
            errors.append(f"acceptance uniqueness drifted: {name}")

    acceptance_checks = {
        value.name for value in acceptance_table.constraints
        if isinstance(value, CheckConstraint)
    }
    for name in {
        "ck_preparation_repair_acceptance_versions",
        "ck_preparation_repair_acceptance_schedule_version",
        "ck_preparation_repair_acceptance_method",
        "ck_preparation_repair_acceptance_hash_lengths",
        "ck_preparation_repair_acceptance_reason_nonblank",
    }:
        if name not in acceptance_checks:
            errors.append(f"acceptance check constraint missing: {name}")

    schedule_table = DBPersistedPreparationSchedule.__table__
    for column in [
        "derivation_method",
        "source_repair_proposal_id",
        "source_repair_proposal_version",
        "source_repair_request_hash",
        "source_repair_result_hash",
        "source_revised_request_hash",
        "source_repaired_response_hash",
    ]:
        if column not in schedule_table.columns:
            errors.append(f"persisted schedule lacks derivation column: {column}")
    schedule_indexes = {
        value.name: tuple(column.name for column in value.columns)
        for value in schedule_table.indexes
        if isinstance(value, Index)
    }
    if schedule_indexes.get("ix_persisted_schedule_derivation_created") != (
        "derivation_method",
        "created_at",
        "id",
    ):
        errors.append("persisted schedule derivation index drifted")

    _require(
        sources["domain"],
        {
            "class PreparationRepairProposalAcceptRequest",
            "acknowledge_creates_new_draft_only: Literal[True]",
            "acknowledged_task_ids",
            "class PreparationRepairProposalAcceptedDraftView",
            "approval_performed: Literal[False]",
            "execution_performed: Literal[False]",
            "accepted_schedule_hash",
        },
        "acceptance domain",
        errors,
    )
    _require(
        sources["acceptance_service"],
        {
            "def accept_repair_proposal",
            "repair_acceptance_acknowledgement_mismatch",
            "repair_acceptance_source_has_execution_history",
            "replay_preparation_schedule(",
            "PreparationScheduleDerivationMethod.REPAIR",
            "status=PreparationScheduleStatus.DRAFT.value",
            "source_repair_proposal_id=proposal.id",
            "PreparationRepairProposalEventType.ACCEPTED",
            "approval_performed=False",
            "execution_performed=False",
            "_repaired_combined_schedule_hash",
        },
        "acceptance service",
        errors,
    )
    for forbidden in [
        "PreparationScheduleStatus.APPROVED.value",
        "PreparationScheduleEventType.APPROVED",
        "record_task_execution_event(",
        "complete_schedule_with_execution_guard(",
        "source.status =",
        "source.version +=",
        "source.schedule_payload =",
    ]:
        if forbidden in sources["acceptance_service"]:
            errors.append(f"acceptance service contains forbidden action: {forbidden}")

    _require(
        sources["approval_service"],
        {
            "def approve_schedule_authoritative",
            "if method == ORIGINAL_SCHEDULER_METHOD",
            "transition_schedule(",
            "_validate_repaired_approval_replay(",
            "PreparationScheduleDerivationMethod.REPAIR",
            "method_aware_replay_verified",
            "source_repair_proposal_id",
            "repair_schedule_hash_mismatch",
        },
        "approval service",
        errors,
    )
    _require(
        sources["proposal_routes"],
        {
            '"/{proposal_id}/accept"',
            '"/{proposal_id}/acceptance"',
            "PreparationRepairProposalAcceptedDraftView",
            "HouseholdRole.EDITOR",
            "HouseholdRole.VIEWER",
            "accept_repair_proposal(",
        },
        "proposal routes",
        errors,
    )
    _require(
        sources["schedule_routes"],
        {
            "approve_schedule_authoritative",
            "HouseholdRole.OWNER",
            "return approve_schedule_authoritative(",
        },
        "schedule routes",
        errors,
    )

    _require(
        sources["migration"],
        {
            'revision = "20260802_0017"',
            'down_revision = "20260802_0016"',
            '"preparation_repair_proposal_acceptances"',
            '"derivation_method"',
            '"source_repair_proposal_id"',
            "Cannot downgrade repair acceptance migration",
        },
        "acceptance migration",
        errors,
    )
    _require(
        sources["tests"],
        {
            "test_acceptance_creates_one_new_draft_and_preserves_source",
            "test_acceptance_requires_exact_changed_task_acknowledgements",
            "test_acceptance_is_exactly_idempotent_and_cross_key_repeat_fails",
            "test_acceptance_rejects_stale_identity_before_persistence",
            "test_repaired_draft_requires_method_aware_owner_approval",
            "test_repaired_draft_approval_fails_after_proposal_hash_tamper",
        },
        "acceptance tests",
        errors,
    )
    _require(
        sources["api_tests"],
        {
            "test_editor_can_accept_into_draft_and_view_immutable_acceptance",
            "test_acceptance_rejects_incomplete_acknowledgement",
            "approval_performed",
            "execution_performed",
        },
        "acceptance API tests",
        errors,
    )
    _require(
        sources["docs"],
        {
            "creates exactly one new preparation schedule in `draft` state",
            "Owner approval remains a different endpoint and action",
            "The source schedule is never updated or deleted",
            "No step implies a later step",
        },
        "acceptance documentation",
        errors,
    )

    return {
        "valid": not errors,
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "proposal_statuses": sorted(statuses),
        "proposal_events": sorted(events),
        "acceptance_table": acceptance_table.name,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
