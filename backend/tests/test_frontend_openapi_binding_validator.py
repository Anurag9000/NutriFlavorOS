from __future__ import annotations

from scripts.validate_frontend_openapi_bindings import (
    validate_frontend_openapi_bindings,
)


def test_frontend_bindings_match_generated_openapi():
    report = validate_frontend_openapi_bindings()
    assert report["contract_version"] == "2026-08-01.2"
    assert report["openapi_version"] == "0.6.0"
    assert report["typescript_source"] == "frontend/src/lib/platformApi.ts"
    assert set(report["schemas"]) == {
        "IngredientConversionVersionView",
        "StoragePolicyVersionView",
        "ConversionApplicationResult",
        "EvidenceLifecycleEventView",
    }
    assert set(report["enums"]) == {
        "EvidenceRecordStatus",
        "EvidenceTargetKind",
        "EvidenceLifecycleAction",
    }
    assert len(report["operations"]) == 6
    assert all(value["route_fragment_present"] for value in report["operations"])
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
