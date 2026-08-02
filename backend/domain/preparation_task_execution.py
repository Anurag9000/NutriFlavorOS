"""Strict contracts for explicit preparation task execution evidence."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field, model_validator

from backend.domain.preparation import ScheduledPreparationTask
from backend.domain.preparation_operations import (
    PersistedPreparationScheduleView,
    StrictPreparationOperationsModel,
)


class PreparationTaskExecutionEventType(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class PreparationTaskExecutionState(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class PreparationTaskExecutionEventCreate(StrictPreparationOperationsModel):
    expected_schedule_version: int = Field(ge=1)
    actual_minute: int = Field(ge=0, le=10080)
    reason: Optional[str] = Field(default=None, max_length=1000)
    notes: Optional[str] = Field(default=None, max_length=4000)
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_text(self):
        self.reason = (
            " ".join(self.reason.strip().split()) if self.reason else None
        )
        self.notes = self.notes.strip() if self.notes else None
        return self


class PreparationTaskExecutionEventView(StrictPreparationOperationsModel):
    id: int
    schedule_id: int
    household_id: str
    task_id: str
    event_type: PreparationTaskExecutionEventType
    actor_user_id: str
    from_state: PreparationTaskExecutionState
    to_state: PreparationTaskExecutionState
    planned_start_minute: int
    planned_finish_minute: int
    actual_minute: int
    deviation_minutes: int
    reason: Optional[str]
    notes: Optional[str]
    metadata: Dict[str, Any]
    idempotency_key: str
    request_fingerprint: str
    schedule_version_before: int
    schedule_version_after: int
    created_at: str


class PreparationTaskExecutionTaskView(StrictPreparationOperationsModel):
    task: ScheduledPreparationTask
    state: PreparationTaskExecutionState
    latest_event_id: Optional[int] = None
    started_actual_minute: Optional[int] = None
    completed_actual_minute: Optional[int] = None
    skipped_actual_minute: Optional[int] = None
    terminal_reason: Optional[str] = None


class PreparationTaskExecutionOverview(StrictPreparationOperationsModel):
    schedule: PersistedPreparationScheduleView
    tasks: List[PreparationTaskExecutionTaskView]
    events: List[PreparationTaskExecutionEventView]
    planned_count: int
    in_progress_count: int
    completed_count: int
    skipped_count: int
    terminal_count: int
    remaining_count: int


class PreparationTaskExecutionMutationView(StrictPreparationOperationsModel):
    schedule: PersistedPreparationScheduleView
    task: PreparationTaskExecutionTaskView
    event: PreparationTaskExecutionEventView
