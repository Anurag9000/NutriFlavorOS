#!/usr/bin/env python3
"""Validate deterministic preparation replay contracts."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.domain.preparation_schedule_replay import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
    PreparationScheduleDerivationMethod,
)

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "backend/domain/preparation_schedule_replay.py"
SERVICE = ROOT / "backend/services/preparation_schedule_replay_service.py"
TESTS = ROOT / "backend/tests/test_preparation_schedule_replay.py"
DOCS = ROOT / "docs/PREPARATION_SCHEDULE_REPLAY.md"


def _source(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        errors.append(f"missing file: {path.relative_to(ROOT)}")
        return ""
    value = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(value, filename=str(path.relative_to(ROOT)))
    return value


def validate_contract() -> dict:
    errors: list[str] = []
    domain = _source(DOMAIN, errors)
    service = _source(SERVICE, errors)
    tests = _source(TESTS, errors)
    docs = _source(DOCS, errors)

    expected = {ORIGINAL_SCHEDULER_METHOD, REPAIR_SCHEDULER_METHOD}
    observed = {item.value for item in PreparationScheduleDerivationMethod}
    if observed != expected:
        errors.append("derivation method registry drifted")

    fragments = {
        "domain": (
            domain,
            [
                "class OriginalPreparationScheduleReplay",
                "class RepairedPreparationScheduleReplay",
                "class PreparationScheduleReplayEvidence",
                "expected_repair_request_hash",
                "expected_repair_result_hash",
                "expected_revised_request_hash",
                "expected_response_hash",
            ],
        ),
        "service": (
            service,
            [
                "def replay_original_schedule",
                "def replay_repaired_schedule",
                "def replay_preparation_schedule",
                "build_preparation_schedule(envelope.request)",
                "repair_preparation_schedule(envelope.repair_request)",
                "unknown_schedule_derivation_method",
                "original_replay_output_mismatch",
                "repair_replay_output_mismatch",
                "allow_nan=False",
            ],
        ),
        "tests": (
            tests,
            [
                "test_original_scheduler_replay_is_hash_exact_and_deterministic",
                "test_repair_replay_is_hash_exact_and_preserves_advisory_result",
                "test_dispatch_rejects_unknown_method_and_mixed_envelopes",
                "test_original_replay_rejects_request_and_response_hash_drift",
                "test_repair_replay_rejects_request_result_and_response_hash_drift",
                "test_repair_envelope_rejects_wrong_method_or_preaccepted_result",
                "test_repair_replay_detects_tampered_stored_result_even_with_valid_model",
            ],
        ),
        "docs": (
            docs,
            [
                "Original deterministic scheduler replay",
                "Minimal-change repair replay",
                "No database mutation",
                "accepted repaired draft",
            ],
        ),
    }
    for label, (source, required) in fragments.items():
        for fragment in required:
            if fragment not in source:
                errors.append(f"{label} lacks: {fragment}")

    forbidden = [
        "from sqlalchemy",
        "Session",
        "get_db",
        "db.query",
        "db.add",
        "db.commit",
        "DBPersistedPreparationSchedule",
        "transition_schedule(",
        "create_persisted_schedule(",
    ]
    for fragment in forbidden:
        if fragment in service:
            errors.append(f"replay service contains persistence fragment: {fragment}")

    return {
        "valid": not errors,
        "methods": sorted(observed),
        "files": [
            str(DOMAIN.relative_to(ROOT)),
            str(SERVICE.relative_to(ROOT)),
            str(TESTS.relative_to(ROOT)),
            str(DOCS.relative_to(ROOT)),
        ],
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
