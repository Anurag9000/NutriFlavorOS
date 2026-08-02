"""Contracts for deriving and confirming preparation occurrences from plans."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field, model_validator

from backend.domain.household_plan_lifecycle import StrictHouseholdPlanModel
from backend.domain.preparation_evidence import DurationPolicy
from backend.domain.preparation_operations import PreparationOccurrenceSetDocument


class PreparationProfileAvailability(str, Enum):
    REVIEWED_COMPATIBLE = "reviewed_compatible"
    REVIEWED_INCOMPATIBLE_SERVINGS = "reviewed_incompatible_servings"
    MISSING_REVIEWED_PROFILE = "missing_reviewed_profile"


class ApprovedPlanOccurrenceCandidate(StrictHouseholdPlanModel):
    occurrence_id: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    day: int = Field(ge=1, le=366)
    meal_slot: str = Field(min_length=1, max_length=120)
    recipe_id: str = Field(min_length=1, max_length=240)
    recipe_name: str = Field(min_length=1, max_length=300)
    source_recipe_servings: float = Field(gt=0, le=1000)
    planned_portion_multiplier: float = Field(gt=0, le=1000)
    planned_servings: float = Field(gt=0, le=1000)
    preparation_profile_status: PreparationProfileAvailability
    preparation_profile_id: Optional[int] = Field(default=None, ge=1)
    preparation_profile_version: Optional[str] = None
    preparation_profile_content_hash: Optional[str] = None
    supported_servings_min: Optional[float] = Field(default=None, gt=0, le=1000)
    supported_servings_max: Optional[float] = Field(default=None, gt=0, le=1000)
    warnings: List[str] = Field(default_factory=list)


class ApprovedPlanOccurrenceCandidatesView(StrictHouseholdPlanModel):
    household_id: str
    source_plan_id: int = Field(ge=1)
    source_plan_version: int = Field(ge=1)
    generated_at: str
    candidates: List[ApprovedPlanOccurrenceCandidate]
    reviewed_compatible_count: int = Field(ge=0)
    unresolved_profile_count: int = Field(ge=0)
    warnings: List[str] = Field(default_factory=list)


class PlanOccurrenceConfirmation(StrictHouseholdPlanModel):
    occurrence_id: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    include: bool = True
    servings: Optional[float] = Field(default=None, gt=0, le=1000)
    required_finish_minute: Optional[int] = Field(
        default=None,
        ge=1,
        le=10080,
    )
    priority: int = Field(default=0, ge=-1000, le=1000)

    @model_validator(mode="after")
    def require_included_values(self):
        if self.include:
            if self.servings is None:
                raise ValueError("included occurrences require servings")
            if self.required_finish_minute is None:
                raise ValueError(
                    "included occurrences require required_finish_minute"
                )
        return self


class ConfirmPlanOccurrenceSetRequest(StrictHouseholdPlanModel):
    expected_plan_version: int = Field(ge=1)
    occurrence_set_version: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    duration_policy: DurationPolicy = DurationPolicy.CONSERVATIVE_MAX
    confirmations: List[PlanOccurrenceConfirmation] = Field(
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_confirmation_ids(self):
        identifiers = [value.occurrence_id for value in self.confirmations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("confirmation occurrence_id values must be unique")
        if not any(value.include for value in self.confirmations):
            raise ValueError("at least one occurrence must be included")
        self.confirmations = sorted(
            self.confirmations,
            key=lambda value: value.occurrence_id,
        )
        return self


class ConfirmedPlanOccurrenceSetView(StrictHouseholdPlanModel):
    household_id: str
    source_plan_id: int = Field(ge=1)
    source_plan_version: int = Field(ge=1)
    occurrence_set: PreparationOccurrenceSetDocument
    profile_versions: Dict[str, str]
    confirmed_count: int = Field(ge=1)
    excluded_count: int = Field(ge=0)
    warnings: List[str] = Field(default_factory=list)
