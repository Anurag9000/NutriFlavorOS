"""Strict contracts for compiling confirmed approved-plan occurrences."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field, model_validator

from backend.domain.household_plan_lifecycle import StrictHouseholdPlanModel
from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_operations import PreparationOccurrenceSetDocument


class ApprovedPlanPreparationCompileRequest(StrictHouseholdPlanModel):
    expected_plan_version: int = Field(ge=1)
    calendar_version_id: int = Field(ge=1)
    occurrence_set: PreparationOccurrenceSetDocument
    profile_versions: Dict[str, str]
    granularity_minutes: int = Field(default=5, ge=1, le=60)

    @model_validator(mode="after")
    def validate_profile_recipe_set(self):
        expected = sorted(
            {value.recipe_id for value in self.occurrence_set.occurrences}
        )
        supplied = sorted(self.profile_versions)
        if expected != supplied:
            raise ValueError(
                "profile_versions recipes must exactly match occurrence recipes"
            )
        normalized: Dict[str, str] = {}
        for recipe_id, identity in self.profile_versions.items():
            recipe_key = recipe_id.strip()
            identity_value = identity.strip()
            if not recipe_key or not identity_value:
                raise ValueError("profile_versions cannot contain blank values")
            normalized[recipe_key] = identity_value
        self.profile_versions = dict(sorted(normalized.items()))
        return self


class ApprovedPlanPreparationCompileView(StrictHouseholdPlanModel):
    household_id: str
    source_plan_id: int = Field(ge=1)
    source_plan_version: int = Field(ge=1)
    calendar_version_id: int = Field(ge=1)
    calendar_version: str
    calendar_content_hash: str
    occurrence_set: PreparationOccurrenceSetDocument
    profile_versions: Dict[str, str]
    schedule_request: PreparationScheduleRequest
    schedule_response: PreparationScheduleResponse
    partial: bool
    execution_status: str
    warnings: List[str] = Field(default_factory=list)


class ReviewedPreparationTaskTemplate(StrictHouseholdPlanModel):
    template_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    name: str = Field(min_length=1, max_length=240)
    duration_min_minutes: int = Field(ge=1, le=1440)
    duration_max_minutes: int = Field(ge=1, le=1440)
    resource_demands: Dict[str, int]
    dependencies: List[str] = Field(default_factory=list, max_length=100)
    active_work: bool
    unattended_allowed: bool
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_template(self):
        if self.duration_max_minutes < self.duration_min_minutes:
            raise ValueError(
                "duration_max_minutes cannot be below duration_min_minutes"
            )
        invalid_demands = [
            key
            for key, value in self.resource_demands.items()
            if not key.strip() or value < 1
        ]
        if invalid_demands:
            raise ValueError(
                "resource demands require nonblank IDs and positive integers"
            )
        normalized_dependencies = [value.strip() for value in self.dependencies]
        if any(not value for value in normalized_dependencies):
            raise ValueError("task-template dependency IDs cannot be blank")
        if self.template_id in normalized_dependencies:
            raise ValueError("task template cannot depend on itself")
        if len(normalized_dependencies) != len(set(normalized_dependencies)):
            raise ValueError("task-template dependencies must be unique")
        self.dependencies = normalized_dependencies
        self.resource_demands = dict(sorted(self.resource_demands.items()))
        return self
