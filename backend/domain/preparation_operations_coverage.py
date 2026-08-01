"""Household preparation-operations provenance coverage contracts."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field

from backend.domain.preparation_operations import StrictPreparationOperationsModel


class PreparationOperationsCoverageView(StrictPreparationOperationsModel):
    """Descriptive coverage only; never a correctness or safety score."""

    household_id: str
    generated_at: str
    calendar_total: int = Field(ge=0)
    reviewed_calendar_total: int = Field(ge=0)
    active_reviewed_calendar_count: int = Field(ge=0)
    schedule_total: int = Field(ge=0)
    schedule_status_counts: Dict[str, int]
    replay_status_counts: Dict[str, int]
    occurrence_document_count: int = Field(ge=0)
    scheduler_request_count: int = Field(ge=0)
    replayable_schedule_count: int = Field(ge=0)
    replayable_draft_count: int = Field(ge=0)
    source_plan_linked_count: int = Field(ge=0)
    event_total: int = Field(ge=0)
    occurrence_document_coverage: float = Field(ge=0.0, le=1.0)
    scheduler_request_coverage: float = Field(ge=0.0, le=1.0)
    replayable_schedule_coverage: float = Field(ge=0.0, le=1.0)
    latest_calendar_created_at: Optional[str]
    latest_schedule_created_at: Optional[str]
    warnings: List[str] = Field(default_factory=list)
