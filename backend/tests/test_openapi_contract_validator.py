from __future__ import annotations

from scripts.validate_openapi_contracts import validate_openapi_contract


def test_generated_openapi_matches_required_product_contract():
    report = validate_openapi_contract()
    assert report["contract_version"] == "2026-08-01.4"
    assert report["api_version"] == "0.7.0"
    assert "OAuth2PasswordBearer" in report["security_schemes"]
    assert {
        "IngredientConversionVersionView",
        "StoragePolicyVersionView",
        "ConversionApplicationResult",
        "EvidenceLifecycleEventView",
        "CompileAndScheduleResponse",
        "ResourceCalendarVersionView",
        "PersistedPreparationScheduleView",
        "PreparationScheduleEventView",
    } <= set(report["required_schemas"])
    assert {
        "/api/v1/households/{household_id}/preparation-operations/resource-calendars",
        "/api/v1/households/{household_id}/preparation-operations/schedules",
        "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/approve",
        "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/events",
    } <= set(report["required_paths"])
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
