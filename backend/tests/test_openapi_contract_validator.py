from __future__ import annotations

from scripts.validate_openapi_contracts import validate_openapi_contract


def test_generated_openapi_matches_required_product_contract():
    report = validate_openapi_contract()
    assert report["contract_version"] == "2026-08-01.3"
    assert report["api_version"] == "0.6.0"
    assert "OAuth2PasswordBearer" in report["security_schemes"]
    assert {
        "IngredientConversionVersionView",
        "StoragePolicyVersionView",
        "ConversionApplicationResult",
        "EvidenceLifecycleEventView",
        "CompileAndScheduleResponse",
    } <= set(report["required_schemas"])
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
