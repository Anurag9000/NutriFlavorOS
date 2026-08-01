from __future__ import annotations

from pathlib import Path

from scripts.validate_frontend_openapi_bindings import (
    validate_frontend_openapi_bindings,
)


ROOT = Path(__file__).resolve().parents[2]


def test_preparation_operations_frontend_bindings_match_openapi():
    report = validate_frontend_openapi_bindings(
        contract_path=(
            ROOT
            / "contracts"
            / "preparation_operations_frontend_bindings.json"
        )
    )
    assert report["contract_version"] == "2026-08-01.1"
    assert report["openapi_version"] == "0.7.0"
    assert {
        "ResourceCalendarVersionView",
        "PersistedPreparationScheduleView",
        "PreparationScheduleEventView",
    } <= set(report["schemas"])
    assert len(report["operations"]) == 11
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
