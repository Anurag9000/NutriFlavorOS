"""Reviewed recipe-level preparation evidence and task compilation contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from backend.domain.preparation import PreparationTask


class PreparationEvidenceStatus(str, Enum):
    DRAFT = "draft"
    EXTERNAL_UNVERIFIED = "external_unverified"
    REVIEWED = "reviewed"


class DurationPolicy(str, Enum):
    CONSERVATIVE_MAX = "conservative_max"
    OPTIMISTIC_MIN = "optimistic_min"


class PreparationTaskTemplate(BaseModel):
    template_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    name: str = Field(min_length=1, max_length=240)
    duration_min_minutes: int = Field(ge=1, le=1440)
    duration_max_minutes: int = Field(ge=1, le=1440)
    resource_demands: Dict[str, int] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list, max_length=100)
    active_work: bool = True
    unattended_allowed: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_template(self):
        if self.duration_max_minutes < self.duration_min_minutes:
            raise ValueError("duration_max_minutes cannot be less than duration_min_minutes")
        if self.template_id in self.dependencies:
            raise ValueError("a preparation task template cannot depend on itself")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("task template dependencies must be unique")
        for resource_id, demand in self.resource_demands.items():
            if not resource_id.strip() or demand < 1:
                raise ValueError(
                    "resource demands must use non-empty IDs and positive integers"
                )
        return self


class RecipePreparationProfileInput(BaseModel):
    recipe_id: str = Field(min_length=1, max_length=240)
    schema_version: str = Field(default="1", pattern=r"^[0-9]+$")
    supported_servings_min: float = Field(gt=0, le=1000)
    supported_servings_max: float = Field(gt=0, le=1000)
    task_templates: List[PreparationTaskTemplate] = Field(min_length=1, max_length=100)
    source_name: str = Field(min_length=1, max_length=300)
    source_url: str = Field(min_length=1, max_length=2000)
    source_version: str = Field(min_length=1, max_length=200)
    evidence_status: PreparationEvidenceStatus = PreparationEvidenceStatus.DRAFT
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=4000)
    active: bool = True

    @model_validator(mode="after")
    def validate_profile(self):
        if self.supported_servings_max < self.supported_servings_min:
            raise ValueError(
                "supported_servings_max cannot be less than supported_servings_min"
            )
        identifiers = [value.template_id for value in self.task_templates]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("task template identifiers must be unique")
        identifier_set = set(identifiers)
        graph = {
            value.template_id: tuple(value.dependencies)
            for value in self.task_templates
        }
        for template in self.task_templates:
            unknown = sorted(set(template.dependencies) - identifier_set)
            if unknown:
                raise ValueError(
                    f"template {template.template_id} references unknown dependencies: "
                    + ", ".join(unknown)
                )

        state: Dict[str, int] = {}
        trail: List[str] = []

        def visit(identifier: str) -> None:
            marker = state.get(identifier, 0)
            if marker == 2:
                return
            if marker == 1:
                start = trail.index(identifier)
                cycle = trail[start:] + [identifier]
                raise ValueError(
                    "preparation template dependency cycle: " + " -> ".join(cycle)
                )
            state[identifier] = 1
            trail.append(identifier)
            for dependency in graph[identifier]:
                visit(dependency)
            trail.pop()
            state[identifier] = 2

        for identifier in sorted(graph):
            visit(identifier)

        if self.evidence_status == PreparationEvidenceStatus.REVIEWED:
            if self.reviewed_at is None:
                raise ValueError("reviewed evidence requires reviewed_at")
            if not self.reviewed_by or not self.reviewed_by.strip():
                raise ValueError("reviewed evidence requires reviewed_by")
        return self


class RecipePreparationProfileView(RecipePreparationProfileInput):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecipePreparationOccurrence(BaseModel):
    occurrence_id: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    recipe_id: str = Field(min_length=1, max_length=240)
    required_finish_minute: int = Field(ge=1, le=10080)
    servings: float = Field(gt=0, le=1000)
    priority: int = Field(default=0, ge=-1000, le=1000)


class BuildPreparationTasksRequest(BaseModel):
    occurrences: List[RecipePreparationOccurrence] = Field(
        min_length=1,
        max_length=500,
    )
    duration_policy: DurationPolicy = DurationPolicy.CONSERVATIVE_MAX
    reviewed_only: bool = True

    @model_validator(mode="after")
    def validate_occurrences(self):
        identifiers = [value.occurrence_id for value in self.occurrences]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("occurrence_id values must be unique")
        return self


class UnresolvedPreparationOccurrence(BaseModel):
    occurrence_id: str
    recipe_id: str
    reason_code: str
    message: str


class BuildPreparationTasksResponse(BaseModel):
    tasks: List[PreparationTask]
    unresolved: List[UnresolvedPreparationOccurrence]
    profile_versions: Dict[str, str]
    duration_policy: DurationPolicy
    warnings: List[str] = Field(default_factory=list)
