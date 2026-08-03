from __future__ import annotations

from scripts.validate_openapi_contracts import validate_openapi_contract


def test_generated_openapi_matches_required_product_contract():
    report = validate_openapi_contract()
    assert report["contract_version"] == "2026-08-03.2"
    assert report["api_version"] == "0.15.4"
    assert "OAuth2PasswordBearer" in report["security_schemes"]
    assert {
        "IngredientConversionVersionView",
        "StoragePolicyVersionView",
        "ConversionApplicationResult",
        "EvidenceLifecycleEventView",
        "CompileAndScheduleResponse",
        "PreparationScheduleRepairResult",
        "ResourceCalendarVersionView",
        "PersistedPreparationScheduleView",
        "PreparationScheduleDerivationEvidenceView",
        "PreparationScheduleDerivationCoverageView",
        "PreparationScheduleEventView",
        "PreparationTaskExecutionEligibilityView",
        "PreparationScheduleSupportExport",
        "PreparationRepairProposalCreateRequest",
        "PreparationRepairProposalRejectRequest",
        "PreparationRepairProposalInvalidateRequest",
        "PreparationRepairProposalAcceptRequest",
        "PreparationRepairProposalView",
        "PreparationRepairProposalEventView",
        "PreparationRepairProposalAcceptanceView",
        "PreparationRepairProposalAcceptedDraftView",
    } <= set(report["required_schemas"])
    assert {
        "/api/v1/preparation/schedule/repair",
        "/api/v1/households/{household_id}/preparation-operations/resource-calendars",
        "/api/v1/households/{household_id}/preparation-operations/schedules",
        "/api/v1/households/{household_id}/preparation-operations/schedule-derivation-coverage",
        "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/derivation",
        "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/support-export",
        "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/task-execution-eligibility",
        "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/approve",
        "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/events",
        "/api/v1/households/{household_id}/preparation-operations/repair-proposals",
        "/api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}",
        "/api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/acceptance",
        "/api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/events",
        "/api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/accept",
        "/api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/reject",
        "/api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/invalidate",
    } <= set(report["required_paths"])
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
