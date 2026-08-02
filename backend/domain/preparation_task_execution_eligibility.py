"""Strict read-only eligibility evidence for preparation task execution."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from backend.domain.preparation_repair import StrictRepairModel


class PreparationTaskExecutionEligibilityReason(str, Enum):
    ELIGIBLE = "eligible"
    SCHEDULE_NOT_APPROVED = "schedule_not_approved"
    SOURCE_HAS_ACCEPTED_REPLACEMENT = (
        "source_schedule_has_accepted_replacement"
    )


class PreparationTaskExecutionEligibilityView(StrictRepairModel):
    schedule_id: int = Field(ge=1)
    household_id: str
    schedule_version: int = Field(ge=1)
    schedule_status: str
    eligible: bool
    reason_code: PreparationTaskExecutionEligibilityReason
    task_event_count: int = Field(ge=0)
    accepted_proposal_id: Optional[int]
    acceptance_id: Optional[int]
    replacement_schedule_id: Optional[int]
    replacement_schedule_status: Optional[str]
    replacement_schedule_version: Optional[int]

    @model_validator(mode="after")
    def validate_reason_partition(self):
        replacement_fields = [
            self.accepted_proposal_id,
            self.acceptance_id,
            self.replacement_schedule_id,
            self.replacement_schedule_status,
            self.replacement_schedule_version,
        ]
        if self.reason_code == PreparationTaskExecutionEligibilityReason.ELIGIBLE:
            if not self.eligible:
                raise ValueError("eligible reason requires eligible=true")
            if self.schedule_status != "approved":
                raise ValueError("eligible execution requires approved schedule")
            if any(value is not None for value in replacement_fields):
                raise ValueError("eligible schedule cannot expose replacement block")
        elif (
            self.reason_code
            == PreparationTaskExecutionEligibilityReason.SCHEDULE_NOT_APPROVED
        ):
            if self.eligible:
                raise ValueError("non-approved schedule cannot be eligible")
            if self.schedule_status == "approved":
                raise ValueError("approved schedule needs a different reason")
            if any(value is not None for value in replacement_fields):
                raise ValueError("status-only block cannot expose replacement evidence")
        elif (
            self.reason_code
            == PreparationTaskExecutionEligibilityReason.SOURCE_HAS_ACCEPTED_REPLACEMENT
        ):
            if self.eligible:
                raise ValueError("replaced source cannot be execution eligible")
            if any(value is None for value in replacement_fields):
                raise ValueError("replacement block requires complete replacement evidence")
        return self
