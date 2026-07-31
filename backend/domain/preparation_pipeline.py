"""Integrated reviewed-evidence compilation and resource scheduling contracts."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from backend.domain.preparation import (
    PreparationResource,
    PreparationScheduleResponse,
)
from backend.domain.preparation_evidence import (
    BuildPreparationTasksResponse,
    DurationPolicy,
    RecipePreparationOccurrence,
)


class CompileAndScheduleRequest(BaseModel):
    occurrences: List[RecipePreparationOccurrence] = Field(
        min_length=1,
        max_length=500,
    )
    duration_policy: DurationPolicy = DurationPolicy.CONSERVATIVE_MAX
    reviewed_only: bool = True
    allow_partial: bool = False
    horizon_minutes: int = Field(default=24 * 60, ge=1, le=10080)
    granularity_minutes: int = Field(default=5, ge=1, le=60)
    resources: List[PreparationResource] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_pipeline_request(self):
        occurrence_ids = [value.occurrence_id for value in self.occurrences]
        if len(occurrence_ids) != len(set(occurrence_ids)):
            raise ValueError("occurrence_id values must be unique")
        resource_ids = [value.resource_id for value in self.resources]
        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("resource_id values must be unique")
        outside = [
            value.occurrence_id
            for value in self.occurrences
            if value.required_finish_minute > self.horizon_minutes
        ]
        if outside:
            raise ValueError(
                "occurrence deadlines exceed the scheduling horizon: "
                + ", ".join(sorted(outside))
            )
        return self


class CompileAndScheduleResponse(BaseModel):
    compilation: BuildPreparationTasksResponse
    schedule: Optional[PreparationScheduleResponse] = None
    partial: bool = False
    execution_status: Literal[
        "scheduled",
        "blocked_unresolved",
        "no_compilable_tasks",
    ]
