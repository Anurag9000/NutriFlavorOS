"""Runtime mutation contracts for persisted preparation operations.

Persisted schedules carry both the complete deterministic request and response.
The service replays the scheduler and accepts only an exact response match.
"""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import Field, model_validator

from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_operations import StrictPreparationOperationsModel


class PersistedScheduleCreateRequest(StrictPreparationOperationsModel):
    calendar_version_id: int = Field(ge=1)
    source_plan_id: Optional[int] = Field(default=None, ge=1)
    source_plan_version: Optional[int] = Field(default=None, ge=1)
    occurrence_set_version: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    occurrence_set_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    profile_versions: Dict[str, str] = Field(default_factory=dict, max_length=1000)
    schedule_request: PreparationScheduleRequest
    schedule_response: PreparationScheduleResponse
    notes: Optional[str] = Field(default=None, max_length=4000)
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )

    @model_validator(mode="after")
    def validate_source_versions(self):
        if (self.source_plan_id is None) != (self.source_plan_version is None):
            raise ValueError(
                "source_plan_id and source_plan_version must be supplied together"
            )
        if self.schedule_response.unscheduled:
            raise ValueError("persisted schedules must be complete")
        if self.schedule_request.horizon_minutes != self.schedule_response.horizon_minutes:
            raise ValueError("schedule request and response horizons differ")
        if self.schedule_request.granularity_minutes != self.schedule_response.granularity_minutes:
            raise ValueError("schedule request and response granularity differs")
        self.notes = self.notes.strip() if self.notes else None
        return self
