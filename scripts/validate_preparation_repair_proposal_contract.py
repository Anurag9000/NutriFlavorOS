#!/usr/bin/env python3
"""Validate preparation repair proposal computation and lifecycle wiring."""

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


def _source(path: str, errors: list[str]) -> str:
    target = ROOT / path
    if not target.is_file():
        errors.append(f"missing repair proposal file: {path}")
        return ""
    value = target.read_text(encoding="utf-8")
    if target.suffix == ".py":
        ast.parse(value, filename=path)
    return value


def _require(
    source: str,
    fragments: set[str],
    label: str,
    errors: list[str],
) -> None:
    for fragment in sorted(fragments):
        if fragment not in source:
            errors.append(f"{label} lacks required fragment: {fragment}")


def _operation(document: dict, path: str, method: str, errors: list[str]) -> dict:
    value = document.get("paths", {}).get(path, {}).get(method)
    if not isinstance(value, dict):
        errors.append(f"missing OpenAPI operation: {method.upper()} {path}")
        return {}
    if not value.get("security"):
        errors.append(f"OpenAPI operation is not authenticated: {method.upper()} {path}")
    return value


def validate_contract() -> dict:
    errors: list[str] = []
    required_files = [
        "backend/domain/preparation_repair_proposals.py",
        "backend/preparation_repair_proposal_models.py",
        "backend/services/preparation_repair_proposal_creation_service.py",
        "backend/services/preparation_repair_proposal_read_service.py",
        "backend/services/preparation_repair_proposal_acceptance_service.py",
        "backend/api/preparation_repair_proposal_routes.py",
        "backend/migrations/versions/20260802_0015_preparation_repair_proposals.py",
        "backend/migrations/versions/20260802_0016_repair_proposal_calendar_identity.py",
        "backend/migrations/versions/20260802_0017_repair_proposal_acceptance.py",
        "backend/tests/test_preparation_repair_proposals.py",
        "backend/tests/test_preparation_repair_proposal_api.py",
        "docs/PREPARATION_REPAIR_PROPOSALS.md",
        "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
    ]
    sources = {path: _source(path, errors) for path in required_files}

    if CURRENT_ALEMBIC_REVISION != "20260802_0017":
        errors.append("runtime migration head must be 20260802_0017")
    for table in [
        "preparation_repair_proposals",
        "preparation_repair_proposal_events",
        "preparation_repair_proposal_acceptances",
    ]:
        if table not in Base.metadata.tables:
            errors.append(f"ORM metadata lacks required table: {table}")
        if table not in CURRENT_REQUIRED_TABLES:
            errors.append(f"runtime schema verification lacks table: {table}")

    proposal_table = DBPreparationRepairProposal.__table__
    event_table = DBPreparationRepairProposalEvent.__table__
    proposal_unique = {
        value.name: tuple(column.name for column in value.columns)
        for value in proposal_table.constraints
        if isinstance(value, UniqueConstraint)
    }
    if proposal_unique.get(
        "uq_preparation_repair_proposal_household_idempotency"
    ) != ("household_id", "creation_idempotency_key"):
        errors.append("proposal idempotency uniqueness drifted")
    if "uq_preparation_repair_proposal_semantic_identity" in proposal_unique:
        errors.append("cross-key semantic uniqueness must remain absent")

    proposal_indexes = {
        value.name: tuple(column.name for column in value.columns)
        for value in proposal_table.indexes
        if isinstance(value, Index)
    }
    if proposal_indexes.get(
        "ix_preparation_repair_proposals_semantic_hashes"
    ) != (
        "source_schedule_id",
        "source_schedule_version",
        "target_calendar_version_id",
        "revised_request_hash",
        "repaired_response_hash",
    ):
        errors.append("proposal semantic evidence index drifted")

    event_unique = {
        value.name: tuple(column.name for column in value.columns)
        for value in event_table.constraints
        if isinstance(value, UniqueConstraint)
    }
    if event_unique.get("uq_preparation_repair_event_proposal_idempotency") != (
        "proposal_id",
        "idempotency_key",
    ):
        errors.append("proposal event idempotency uniqueness drifted")

    for field in [
        "source_schedule_id",
        "expected_source_version",
        "target_calendar_version_id",
        "revised_request",
        "acknowledge_non_acceptance",
        "acknowledge_non_persistence",
        "idempotency_key",
    ]:
        if field not in PreparationRepairProposalCreateRequest.model_fields:
            errors.append(f"proposal create request lacks field: {field}")
    if {value.value for value in PreparationRepairProposalStatus} != {
        "proposed",
        "accepted",
        "rejected",
        "invalidated",
    }:
        errors.append("proposal status enum drifted")
    for field in [
        "accepted",
        "schedule_persistence_performed",
        "accepted_schedule_id",
        "accepted_schedule_hash",
        "accepted_by_user_id",
        "accepted_at",
        "acceptance_reason",
    ]:
        model_field = PreparationRepairProposalView.model_fields.get(field)
        if model_field is None or not model_field.is_required():
            errors.append(f"proposal view must require lifecycle field: {field}")

    document = app.openapi()
    create_operation = _operation(document, COLLECTION, "post", errors)
    _operation(document, COLLECTION, "get", errors)
    _operation(document, COLLECTION + "/{proposal_id}", "get", errors)
    _operation(document, COLLECTION + "/{proposal_id}/events", "get", errors)
    _operation(document, COLLECTION + "/{proposal_id}/acceptance", "get", errors)
    accept_operation = _operation(
        document,
        COLLECTION + "/{proposal_id}/accept",
        "post",
        errors,
    )
    reject_operation = _operation(
        document,
        COLLECTION + "/{proposal_id}/reject",
        "post",
        errors,
    )
    expected_response_schemas = [
        (create_operation, "PreparationRepairProposalView"),
        (accept_operation, "PreparationRepairProposalAcceptedDraftView"),
        (reject_operation, "PreparationRepairProposalView"),
    ]
    for operation, schema in expected_response_schemas:
        response_schema = (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if response_schema.get("$ref") != f"#/components/schemas/{schema}":
            errors.append(f"proposal response schema drifted: {schema}")
    for path in document.get("paths", {}):
        if path.startswith(COLLECTION) and (
            path.endswith("/approve")
            or path.endswith("/persist")
            or path.endswith("/complete")
            or path.endswith("/execute")
        ):
            errors.append(f"forbidden proposal lifecycle endpoint exposed: {path}")

    creation_source = sources[
        "backend/services/preparation_repair_proposal_creation_service.py"
    ]
    _require(
        creation_source,
        {
            "repair_preparation_schedule(repair_request)",
            "PersistedScheduleCreateRequest.model_validate",
            "allow_partial=False",
            "creation_idempotency_key",
            "creation_request_fingerprint",
            '"accepted": False',
            '"schedule_persistence_performed": False',
            "preparation_repair_proposal_read_service import _proposal_view",
        },
        "proposal creation service",
        errors,
    )
    for forbidden in [
        "DBPersistedPreparationSchedule(",
        "transition_schedule(",
        "record_task_execution_event(",
        "PreparationRepairProposalEventType.ACCEPTED",
    ]:
        if forbidden in creation_source:
            errors.append(f"proposal creation contains forbidden action: {forbidden}")

    routes_source = sources["backend/api/preparation_repair_proposal_routes.py"]
    _require(
        routes_source,
        {
            "preparation_repair_proposal_creation_service",
            "preparation_repair_proposal_read_service",
            "preparation_repair_proposal_acceptance_service",
            '"/{proposal_id}/accept"',
            '"/{proposal_id}/acceptance"',
            '"/{proposal_id}/reject"',
            "HouseholdRole.EDITOR",
            "HouseholdRole.VIEWER",
        },
        "proposal routes",
        errors,
    )
    if "from backend.services.preparation_repair_proposal_service import (" in routes_source:
        errors.append("proposal route imports superseded shared lifecycle functions")

    _require(
        sources["backend/migrations/versions/20260802_0015_preparation_repair_proposals.py"],
        {
            'revision = "20260802_0015"',
            'down_revision = "20260802_0014"',
            '"preparation_repair_proposals"',
            '"preparation_repair_proposal_events"',
        },
        "proposal migration 0015",
        errors,
    )
    _require(
        sources["backend/migrations/versions/20260802_0016_repair_proposal_calendar_identity.py"],
        {
            'revision = "20260802_0016"',
            'down_revision = "20260802_0015"',
            '"ix_preparation_repair_proposals_semantic_hashes"',
        },
        "proposal migration 0016",
        errors,
    )
    _require(
        sources["backend/migrations/versions/20260802_0017_repair_proposal_acceptance.py"],
        {
            'revision = "20260802_0017"',
            'down_revision = "20260802_0016"',
            '"preparation_repair_proposal_acceptances"',
            "accepted",
        },
        "proposal migration 0017",
        errors,
    )

    _require(
        sources["backend/tests/test_preparation_repair_proposals.py"],
        {
            "test_proposal_is_server_recomputed_hash_addressed_and_non_accepted",
            "test_proposal_creation_is_exactly_idempotent_and_conflicting_reuse_fails",
            "test_distinct_request_keys_create_independent_review_records",
            "test_creation_rejects_stale_source_version_and_provenance_drift",
            "test_calendar_supersession_marks_proposal_stale_without_mutating_it",
            "test_proposal_rejection_is_versioned_append_only_and_idempotent",
            "test_proposal_read_fails_closed_after_payload_or_hash_tampering",
        },
        "proposal tests",
        errors,
    )

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
