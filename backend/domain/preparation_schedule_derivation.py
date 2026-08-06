"""Strict public evidence for persisted preparation schedule derivation."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field, model_validator

from backend.domain.preparation_repair import StrictRepairModel
from backend.domain.preparation_schedule_replay import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
    PreparationScheduleDerivationMethod,
)


class PreparationScheduleDerivationEvidenceView(StrictRepairModel):
    schedule_id: int = Field(ge=1)
    household_id: str
    schedule_version: int = Field(ge=1)
    schedule_status: str
    schedule_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    derivation_method: PreparationScheduleDerivationMethod
    evidence_complete: bool

    source_repair_proposal_id: Optional[int]
    source_repair_proposal_version: Optional[int]
    source_repair_acceptance_id: Optional[int]
    source_schedule_id: Optional[int]
    source_schedule_version: Optional[int]

    source_schedule_hash: Optional[str]
    source_schedule_request_hash: Optional[str]
    target_calendar_content_hash: Optional[str]
    repair_request_hash: Optional[str]
    repair_result_hash: Optional[str]
    revised_request_hash: Optional[str]
    repaired_response_hash: Optional[str]

    accepted_by_user_id: Optional[str]
    accepted_at: Optional[str]
    acceptance_reason: Optional[str]
    warnings: List[str]
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def validate_method_partition(self):
        repair_fields = [
            self.source_repair_proposal_id,
            self.source_repair_proposal_version,
            self.source_repair_acceptance_id,
            self.source_schedule_id,
            self.source_schedule_version,
            self.source_schedule_hash,
            self.source_schedule_request_hash,
            self.target_calendar_content_hash,
            self.repair_request_hash,
            self.repair_result_hash,
            self.revised_request_hash,
            self.repaired_response_hash,
            self.accepted_by_user_id,
            self.accepted_at,
            self.acceptance_reason,
        ]
        if self.derivation_method == PreparationScheduleDerivationMethod.ORIGINAL:
            if any(value is not None for value in repair_fields):
                raise ValueError(
                    "original schedule cannot expose repair derivation evidence"
                )
            if not self.evidence_complete:
                raise ValueError("original scheduler evidence must be complete")
        elif self.derivation_method == PreparationScheduleDerivationMethod.REPAIR:
            if any(value is None for value in repair_fields):
                raise ValueError(
                    "repair-derived schedule requires complete acceptance evidence"
                )
            if not self.evidence_complete:
                raise ValueError("repair derivation evidence must be complete")
        else:  # pragma: no cover - enum validation prevents this branch
            raise ValueError("unsupported derivation method")
        return self


__all__ = [
    "ORIGINAL_SCHEDULER_METHOD",
    "REPAIR_SCHEDULER_METHOD",
    "PreparationScheduleDerivationEvidenceView",
]
