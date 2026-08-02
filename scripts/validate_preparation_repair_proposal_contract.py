#!/usr/bin/env python3
"""Validate immutable repair proposal computation and lifecycle wiring."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from sqlalchemy import Index, UniqueConstraint

from backend.database import Base
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalCreateRequest,
    PreparationRepairProposalStatus,
    PreparationRepairProposalView,
)
from backend.main import app
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalEvent,
)
from backend.schema_revision import CURRENT_ALEMBIC_REVISION
from backend.schema_verification import CURRENT_REQUIRED_TABLES


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = (
    "/api/v1/households/{household_id}"
    "/preparation-operations/repair-proposals"
)
FILES = {
    "domain": "backend/domain/preparation_repair_proposals.py",
    "models": "backend/preparation_repair_proposal_models.py",
    "creation": "backend/services/preparation_repair_proposal_creation_service.py",
    "read": "backend/services/preparation_repair_proposal_read_service.py",
    "acceptance": "backend/services/preparation_repair_proposal_acceptance_service.py",
    "source_guard": "backend/services/preparation_repair_source_acceptance_guard_service.py",
    "routes": "backend/api/preparation_repair_proposal_routes.py",
    "migration_0015": "backend/migrations/versions/20260802_0015_preparation_repair_proposals.py",
    "migration_0016": "backend/migrations/versions/20260802_0016_repair_proposal_calendar_identity.py",
    "migration_0017": "backend/migrations/versions/20260802_0017_repair_proposal_acceptance.py",
    "migration_0018": "backend/migrations/versions/20260802_0018_unique_repair_source_acceptance.py",
    "tests": "backend/tests/test_preparation_repair_proposals.py",
    "api_tests": "backend/tests/test_preparation_repair_proposal_api.py",
    "source_tests": "backend/tests/test_preparation_repair_source_acceptance_guard.py",
    "docs": "docs/PREPARATION_REPAIR_PROPOSALS.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing repair proposal file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _operation(document: dict, path: str, method: str, errors: list[str]) -> dict:
    operation = document.get("paths", {}).get(path, {}).get(method)
    if not isinstance(operation, dict):
        errors.append(f"missing OpenAPI operation: {method.upper()} {path}")
        return {}
    if not operation.get("security"):
        errors.append(f"OpenAPI operation is not authenticated: {method.upper()} {path}")
    return operation


def _require(source: str, fragments: set[str], label: str, errors: list[str]) -> None:
    for fragment in sorted(fragments):
        if fragment not in source:
            errors.append(f"{label} lacks required fragment: {fragment}")


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    if CURRENT_ALEMBIC_REVISION != "20260802_0018":
        errors.append("runtime migration head must be 20260802_0018")
    for table in {
        "preparation_repair_proposals",
        "preparation_repair_proposal_events",
        "preparation_repair_proposal_acceptances",
    }:
        if table not in Base.metadata.tables:
            errors.append(f"ORM metadata lacks required table: {table}")
        if table not in CURRENT_REQUIRED_TABLES:
            errors.append(f"runtime schema verification lacks table: {table}")

    proposal_table = DBPreparationRepairProposal.__table__
    proposal_uniques = {
        value.name: tuple(column.name for column in value.columns)
        for value in proposal_table.constraints
        if isinstance(value, UniqueConstraint)
    }
    if proposal_uniques.get(
        "uq_preparation_repair_proposal_household_idempotency"
    ) != ("household_id", "creation_idempotency_key"):
        errors.append("proposal idempotency uniqueness drifted")
    if "uq_preparation_repair_proposal_semantic_identity" in proposal_uniques:
        errors.append("cross-key semantic uniqueness must remain absent")

    proposal_indexes = {
        value.name: tuple(column.name for column in value.columns)
        for value in proposal_table.indexes
        if isinstance(value, Index)
    }
    if proposal_indexes.get("ix_preparation_repair_proposals_semantic_hashes") != (
        "source_schedule_id",
        "source_schedule_version",
        "target_calendar_version_id",
        "revised_request_hash",
        "repaired_response_hash",
    ):
        errors.append("proposal semantic evidence index drifted")

    event_uniques = {
        value.name: tuple(column.name for column in value.columns)
        for value in DBPreparationRepairProposalEvent.__table__.constraints
        if isinstance(value, UniqueConstraint)
    }
    if event_uniques.get("uq_preparation_repair_event_proposal_idempotency") != (
        "proposal_id",
        "idempotency_key",
    ):
        errors.append("proposal event idempotency uniqueness drifted")

    for field in {
        "source_schedule_id",
        "expected_source_version",
        "target_calendar_version_id",
        "revised_request",
        "acknowledge_non_acceptance",
        "acknowledge_non_persistence",
        "idempotency_key",
    }:
        if field not in PreparationRepairProposalCreateRequest.model_fields:
            errors.append(f"proposal create request lacks field: {field}")
    if {value.value for value in PreparationRepairProposalStatus} != {
        "proposed",
        "accepted",
        "rejected",
        "invalidated",
    }:
        errors.append("proposal status enum drifted")
    for field in {
        "accepted",
        "schedule_persistence_performed",
        "accepted_schedule_id",
        "accepted_schedule_hash",
        "accepted_by_user_id",
        "accepted_at",
        "acceptance_reason",
    }:
        model_field = PreparationRepairProposalView.model_fields.get(field)
        if model_field is None or not model_field.is_required():
            errors.append(f"proposal view must require lifecycle field: {field}")

    document = app.openapi()
    operations = {
        "create": _operation(document, COLLECTION, "post", errors),
        "list": _operation(document, COLLECTION, "get", errors),
        "get": _operation(document, COLLECTION + "/{proposal_id}", "get", errors),
        "events": _operation(
            document,
            COLLECTION + "/{proposal_id}/events",
            "get",
            errors,
        ),
        "acceptance": _operation(
            document,
            COLLECTION + "/{proposal_id}/acceptance",
            "get",
            errors,
        ),
        "accept": _operation(
            document,
            COLLECTION + "/{proposal_id}/accept",
            "post",
            errors,
        ),
        "reject": _operation(
            document,
            COLLECTION + "/{proposal_id}/reject",
            "post",
            errors,
        ),
    }
    expected_schemas = {
        "create": "PreparationRepairProposalView",
        "accept": "PreparationRepairProposalAcceptedDraftView",
        "reject": "PreparationRepairProposalView",
    }
    for name, schema_name in expected_schemas.items():
        observed = (
            operations[name]
            .get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
            .get("$ref")
        )
        if observed != f"#/components/schemas/{schema_name}":
            errors.append(f"proposal response schema drifted: {name}")

    _require(
        sources["creation"],
        {
            "repair_preparation_schedule(repair_request)",
            "PersistedScheduleCreateRequest.model_validate",
            "allow_partial=False",
            "creation_idempotency_key",
            "creation_request_fingerprint",
            '"accepted": False',
            '"schedule_persistence_performed": False',
        },
        "proposal creation service",
        errors,
    )
    for forbidden in {
        "create_persisted_schedule(",
        "transition_schedule(",
        "record_task_execution_event(",
    }:
        if forbidden in sources["creation"]:
            errors.append(f"proposal creation contains forbidden action: {forbidden}")

    _require(
        sources["routes"],
        {
            "preparation_repair_proposal_creation_service",
            "preparation_repair_proposal_read_service",
            "accept_repair_proposal_with_source_guard",
            "HouseholdRole.EDITOR",
            "HouseholdRole.VIEWER",
            '"/{proposal_id}/accept"',
            '"/{proposal_id}/acceptance"',
            '"/{proposal_id}/reject"',
        },
        "proposal routes",
        errors,
    )
    _require(
        sources["source_guard"],
        {
            "repair_source_already_has_accepted_replacement",
            "return accept_repair_proposal(",
        },
        "source acceptance guard",
        errors,
    )

    for label, fragments in {
        "migration_0015": {
            'revision = "20260802_0015"',
            'down_revision = "20260802_0014"',
            '"preparation_repair_proposals"',
            '"preparation_repair_proposal_events"',
        },
        "migration_0016": {
            'revision = "20260802_0016"',
            'down_revision = "20260802_0015"',
            "ix_preparation_repair_proposals_semantic_hashes",
        },
        "migration_0017": {
            'revision = "20260802_0017"',
            'down_revision = "20260802_0016"',
            '"preparation_repair_proposal_acceptances"',
        },
        "migration_0018": {
            'revision = "20260802_0018"',
            'down_revision = "20260802_0017"',
            "uq_preparation_repair_acceptance_source_version",
        },
        "tests": {
            "test_proposal_is_server_recomputed_hash_addressed_and_non_accepted",
            "test_proposal_creation_is_exactly_idempotent_and_conflicting_reuse_fails",
            "test_distinct_request_keys_create_independent_review_records",
            "test_proposal_rejection_is_versioned_append_only_and_idempotent",
            "test_proposal_read_fails_closed_after_payload_or_hash_tampering",
        },
        "api_tests": {
            "test_editor_can_accept_into_draft_and_view_immutable_acceptance",
            "test_acceptance_rejects_incomplete_acknowledgement",
        },
        "source_tests": {
            "test_source_guard_rejects_second_proposal_for_same_source_version",
            "test_database_constraint_blocks_direct_service_bypass",
        },
        "docs": {
            "Proposal creation never implies acceptance",
            "Acceptance creates a new draft",
            "one accepted replacement per source schedule version",
        },
    }.items():
        _require(sources[label], fragments, label, errors)

    return {
        "valid": not errors,
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "collection_path": COLLECTION,
        "statuses": sorted(value.value for value in PreparationRepairProposalStatus),
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
