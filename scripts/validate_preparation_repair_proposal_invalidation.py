#!/usr/bin/env python3
"""Validate owner-only append-only repair proposal invalidation."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalEventType,
    PreparationRepairProposalInvalidateRequest,
    PreparationRepairProposalStatus,
)
from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    "/api/v1/households/{household_id}/preparation-operations/"
    "repair-proposals/{proposal_id}/invalidate"
)
FILES = {
    "domain": "backend/domain/preparation_repair_proposals.py",
    "service": "backend/services/preparation_repair_proposal_invalidation_service.py",
    "routes": "backend/api/preparation_repair_proposal_routes.py",
    "tests": "backend/tests/test_preparation_repair_proposal_invalidation.py",
    "api_tests": "backend/tests/test_preparation_repair_proposal_api.py",
    "docs": "docs/PREPARATION_REPAIR_PROPOSALS.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing invalidation file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    fields = PreparationRepairProposalInvalidateRequest.model_fields
    for field in {
        "expected_version",
        "reason",
        "acknowledge_historical_only",
        "idempotency_key",
        "metadata",
    }:
        if field not in fields:
            errors.append(f"invalidation request lacks field: {field}")
    if PreparationRepairProposalStatus.INVALIDATED.value != "invalidated":
        errors.append("proposal invalidated status drifted")
    if PreparationRepairProposalEventType.INVALIDATED.value != "invalidated":
        errors.append("proposal invalidated event drifted")

    operation = app.openapi().get("paths", {}).get(PATH, {}).get("post")
    if not isinstance(operation, dict):
        errors.append("generated OpenAPI lacks proposal invalidation endpoint")
    else:
        if not operation.get("security"):
            errors.append("proposal invalidation endpoint is not authenticated")
        schema = (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if schema.get("$ref") != "#/components/schemas/PreparationRepairProposalView":
            errors.append("proposal invalidation response schema drifted")

    required = {
        "domain": {
            "class PreparationRepairProposalInvalidateRequest",
            "acknowledge_historical_only: Literal[True]",
        },
        "service": {
            "def invalidate_repair_proposal",
            "repair_proposal_not_invalidatable",
            "repair_proposal_invalidation_conflict",
            "observed_stale_reasons",
            '"historical_only": True',
            '"accepted": False',
            '"schedule_persistence_performed": False',
            "PreparationRepairProposalEventType.INVALIDATED",
        },
        "routes": {
            '"/{proposal_id}/invalidate"',
            "PreparationRepairProposalInvalidateRequest",
            "HouseholdRole.OWNER",
            "return invalidate_repair_proposal(",
            "accept_repair_proposal_with_source_guard(",
        },
        "tests": {
            "test_invalidation_is_append_only_historical_and_nonpersistent",
            "test_invalidation_captures_server_observed_stale_reasons",
            "test_invalidation_is_exactly_idempotent_and_conflicting_reuse_fails",
            "test_invalidation_rejects_stale_version_and_terminal_proposals",
            "test_rejection_prevents_later_invalidation",
        },
        "api_tests": {
            "test_acceptance_route_uses_source_version_uniqueness_guard",
            "test_owner_can_invalidate_but_editor_cannot",
        },
        "docs": {
            "Owner-only proposal invalidation",
            "observed stale reasons",
            "acknowledge_historical_only",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks invalidation fragment: {fragment}")

    for forbidden in {
        "create_persisted_schedule(",
        "accept_repair_proposal(",
        "transition_schedule(",
        "record_task_execution_event(",
        "source.status =",
        "source.version +=",
    }:
        if forbidden in sources["service"]:
            errors.append(f"invalidation service contains forbidden action: {forbidden}")

    return {
        "valid": not errors,
        "path": PATH,
        "required_role": "owner",
        "schedule_persistence": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
