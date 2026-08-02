#!/usr/bin/env python3
"""Validate immutable preparation repair proposal contracts and release wiring."""

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
    return target.read_text(encoding="utf-8")


def _require(source: str, fragments: set[str], label: str, errors: list[str]) -> None:
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
        "backend/services/preparation_repair_proposal_service.py",
        "backend/api/preparation_repair_proposal_routes.py",
        "backend/migrations/versions/20260802_0015_preparation_repair_proposals.py",
        "backend/migrations/versions/20260802_0016_repair_proposal_calendar_identity.py",
        "backend/tests/test_preparation_repair_proposals.py",
        "backend/tests/test_preparation_repair_proposal_api.py",
        "docs/PREPARATION_REPAIR_PROPOSALS.md",
    ]
    sources = {path: _source(path, errors) for path in required_files}

    if CURRENT_ALEMBIC_REVISION != "20260802_0016":
        errors.append(
            "runtime migration head must be 20260802_0016 for repair proposals"
        )
    for table in [
        "preparation_repair_proposals",
        "preparation_repair_proposal_events",
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
    expected_idempotency = (
        "household_id",
        "creation_idempotency_key",
    )
    if proposal_unique.get(
        "uq_preparation_repair_proposal_household_idempotency"
    ) != expected_idempotency:
        errors.append("proposal idempotency uniqueness drifted")
    if "uq_preparation_repair_proposal_semantic_identity" in proposal_unique:
        errors.append(
            "cross-key semantic uniqueness must not replace exact request-key idempotency"
        )

    proposal_indexes = {
        value.name: tuple(column.name for column in value.columns)
        for value in proposal_table.indexes
        if isinstance(value, Index)
    }
    expected_semantic_index = (
        "source_schedule_id",
        "source_schedule_version",
        "target_calendar_version_id",
        "revised_request_hash",
        "repaired_response_hash",
    )
    if proposal_indexes.get(
        "ix_preparation_repair_proposals_semantic_hashes"
    ) != expected_semantic_index:
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

    create_fields = PreparationRepairProposalCreateRequest.model_fields
    for field in [
        "source_schedule_id",
        "expected_source_version",
        "target_calendar_version_id",
        "revised_request",
        "acknowledge_non_acceptance",
        "acknowledge_non_persistence",
        "idempotency_key",
    ]:
        if field not in create_fields:
            errors.append(f"proposal create request lacks field: {field}")
    if sorted(value.value for value in PreparationRepairProposalStatus) != [
        "invalidated",
        "proposed",
        "rejected",
    ]:
        errors.append("proposal status enum drifted")
    view_fields = PreparationRepairProposalView.model_fields
    if view_fields.get("accepted") is None or view_fields["accepted"].default is not False:
        errors.append("proposal view must remain non-accepted")
    if (
        view_fields.get("schedule_persistence_performed") is None
        or view_fields["schedule_persistence_performed"].default is not False
    ):
        errors.append("proposal view must report no schedule persistence")

    document = app.openapi()
    create_operation = _operation(document, COLLECTION, "post", errors)
    _operation(document, COLLECTION, "get", errors)
    _operation(document, COLLECTION + "/{proposal_id}", "get", errors)
    _operation(document, COLLECTION + "/{proposal_id}/events", "get", errors)
    reject_operation = _operation(
        document,
        COLLECTION + "/{proposal_id}/reject",
        "post",
        errors,
    )
    for operation, schema in [
        (create_operation, "PreparationRepairProposalView"),
        (reject_operation, "PreparationRepairProposalView"),
    ]:
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
            path.endswith("/accept")
            or path.endswith("/approve")
            or path.endswith("/persist")
            or path.endswith("/complete")
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
        },
        "proposal creation service",
        errors,
    )
    for forbidden in [
        "create_persisted_schedule(",
        "transition_schedule(",
        "record_task_execution_event(",
        "semantic =",
    ]:
        if forbidden in creation_source:
            errors.append(
                f"proposal creation contains forbidden lifecycle/alias fragment: {forbidden}"
            )

    routes_source = sources["backend/api/preparation_repair_proposal_routes.py"]
    _require(
        routes_source,
        {
            "preparation_repair_proposal_creation_service",
            "HouseholdRole.EDITOR",
            "HouseholdRole.VIEWER",
            '"/{proposal_id}/reject"',
        },
        "proposal routes",
        errors,
    )
    if "from backend.services.preparation_repair_proposal_service import (\n    create_repair_proposal" in routes_source:
        errors.append("proposal route uses the superseded shared creation function")

    migration_0015 = sources[
        "backend/migrations/versions/20260802_0015_preparation_repair_proposals.py"
    ]
    migration_0016 = sources[
        "backend/migrations/versions/20260802_0016_repair_proposal_calendar_identity.py"
    ]
    _require(
        migration_0015,
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
        migration_0016,
        {
            'revision = "20260802_0016"',
            'down_revision = "20260802_0015"',
            'drop_constraint(\n            "uq_preparation_repair_proposal_semantic_identity"',
            '"ix_preparation_repair_proposals_semantic_hashes"',
        },
        "proposal migration 0016",
        errors,
    )

    tests_source = sources["backend/tests/test_preparation_repair_proposals.py"]
    _require(
        tests_source,
        {
            "test_proposal_is_server_recomputed_hash_addressed_and_non_accepted",
            "test_proposal_creation_is_exactly_idempotent_and_conflicting_reuse_fails",
            "test_distinct_request_keys_create_independent_review_records",
            "test_creation_rejects_stale_source_version_and_provenance_drift",
            "test_calendar_supersession_marks_proposal_stale_without_mutating_it",
            "test_proposal_rejection_is_versioned_append_only_and_idempotent",
            "test_proposal_read_fails_closed_after_payload_or_hash_tampering",
        },
        "proposal service tests",
        errors,
    )

    for service_path in [
        "backend/services/preparation_repair_proposal_creation_service.py",
        "backend/services/preparation_repair_proposal_service.py",
    ]:
        source = sources.get(service_path, "") or _source(service_path, errors)
        if source:
            ast.parse(source, filename=service_path)

    return {
        "valid": not errors,
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "collection_path": COLLECTION,
        "required_files": required_files,
        "statuses": [value.value for value in PreparationRepairProposalStatus],
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
