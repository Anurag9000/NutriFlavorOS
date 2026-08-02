"""Household-level structural coverage for schedule derivation evidence."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field, model_validator

from backend.domain.preparation_repair import StrictRepairModel


class PreparationScheduleDerivationCoverageView(StrictRepairModel):
    household_id: str
    generated_at: str
    schedule_total: int = Field(ge=0)
    original_schedule_count: int = Field(ge=0)
    repair_schedule_count: int = Field(ge=0)
    unknown_method_count: int = Field(ge=0)
    complete_derivation_count: int = Field(ge=0)
    incomplete_derivation_count: int = Field(ge=0)
    accepted_proposal_count: int = Field(ge=0)
    acceptance_record_count: int = Field(ge=0)
    repaired_draft_count: int = Field(ge=0)
    repaired_approved_count: int = Field(ge=0)
    repaired_execution_history_count: int = Field(ge=0)
    method_counts: Dict[str, int]
    derivation_coverage_ratio: float = Field(ge=0, le=1)
    repair_acceptance_link_coverage_ratio: float = Field(ge=0, le=1)
    latest_acceptance_at: Optional[str]
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_denominators(self):
        if (
            self.original_schedule_count
            + self.repair_schedule_count
            + self.unknown_method_count
            != self.schedule_total
        ):
            raise ValueError("derivation method counts must partition schedules")
        if (
            self.complete_derivation_count
            + self.incomplete_derivation_count
            != self.schedule_total
        ):
            raise ValueError("derivation completeness counts must partition schedules")
        if self.repaired_draft_count + self.repaired_approved_count > self.repair_schedule_count:
            raise ValueError("repair lifecycle counts exceed repair schedule count")
        return self
