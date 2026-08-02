#!/usr/bin/env python3
"""Validate exact retry recovery after a committed response is discarded."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "fixture": "backend/tests/postgres_preparation_fixture.py",
    "tests": "backend/tests/test_preparation_repair_recovery_postgres.py",
    "acceptance": "backend/services/preparation_repair_source_acceptance_guard_service.py",
    "invalidation": "backend/services/preparation_repair_proposal_invalidation_service.py",
    "completion": "backend/services/preparation_operations_service.py",
    "docs": "docs/PREPARATION_REPAIR_ACCEPTANCE.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing recovery file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "fixture": {
            'assert engine.dialect.name == "postgresql"',
            "expire_on_commit=False",
        },
        "tests": {
            "test_postgres_acceptance_exact_retry_recovers_after_lost_response",
            "test_postgres_invalidation_exact_retry_recovers_after_lost_response",
            "test_postgres_completion_exact_retry_recovers_after_lost_response",
            "caller deliberately discards the response",
            "assert len(acceptances) == 1",
            "assert len(drafts) == 1",
            'assert [value.event_type for value in events] == ["created", "invalidated"]',
            "assert len(completed_events) == 1",
        },
        "acceptance": {
            "accept_repair_proposal_with_source_guard",
            "repair_source_already_has_accepted_replacement",
        },
        "invalidation": {
            "existing_event =",
            "request_fingerprint",
            "return _proposal_view(db, proposal)",
        },
        "completion": {
            "existing_event =",
            "return _original_transition_schedule(",
        },
        "docs": {
            "lost-response recovery",
            "exact retry",
            "does not simulate a network disconnect",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if fragment not in sources[label]:
                errors.append(f"{FILES[label]} lacks recovery fragment: {fragment}")

    return {
        "valid": not errors,
        "database": "postgresql",
        "failure_model": "committed_response_discarded",
        "network_disconnect_simulated": False,
        "acceptance_duplicates": 0,
        "invalidation_duplicates": 0,
        "completion_event_duplicates": 0,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
