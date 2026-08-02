"""Strict contracts for deterministic minimal-change preparation repair."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)


class StrictRepairModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PreparationRepairStrategy(str, Enum):
    GREEDY_MIN_CHANGE = "greedy_min_change"
    BOUNDED_EXACT_MIN_CHANGE = "bounded_exact_min_change"


class PreparationRepairWeights(StrictRepairModel):
    unscheduled_task: float = Field(default=1_000_000.0, gt=0)
    changed_task: float = Field(default=10_000.0, gt=0)
    displacement_minute: float = Field(default=10.0, ge=0)
    makespan_minute: float = Field(default=1.0, ge=0)


class PreparationScheduleRepairRequest(StrictRepairModel):
    previous_request: PreparationScheduleRequest
    previous_response: PreparationScheduleResponse
    revised_request: PreparationScheduleRequest
    immutable_task_ids: List[str] = Field(default_factory=list, max_length=10_000)
    strategy: PreparationRepairStrategy = PreparationRepairStrategy.GREEDY_MIN_CHANGE
    allow_partial: bool = False
    weights: PreparationRepairWeights = Field(default_factory=PreparationRepairWeights)
    exact_task_limit: int = Field(default=9, ge=1, le=12)
    exact_candidate_limit_per_task: int = Field(default=80, ge=1, le=500)

    @model_validator(mode="after")
    def validate_request(self):
        immutable = [value.strip() for value in self.immutable_task_ids]
        if any(not value for value in immutable):
            raise ValueError("immutable task IDs cannot be blank")
        if len(immutable) != len(set(immutable)):
            raise ValueError("immutable task IDs must be unique")
        self.immutable_task_ids = sorted(immutable)
        if self.previous_response.unscheduled:
            raise ValueError("previous response must be complete before repair")
        if not self.previous_response.scheduled:
            raise ValueError("previous response must contain deterministic tasks")
        if (
            self.previous_request.horizon_minutes
            != self.previous_response.horizon_minutes
            or self.previous_request.granularity_minutes
            != self.previous_response.granularity_minutes
        ):
            raise ValueError("previous request and response horizons must match")
        return self


class PreparationTaskMovement(StrictRepairModel):
    task_id: str
    previous_start_minute: int = Field(ge=0)
    repaired_start_minute: int = Field(ge=0)
    displacement_minutes: int


class PreparationRepairObjective(StrictRepairModel):
    unscheduled_task_count: int = Field(ge=0)
    changed_task_count: int = Field(ge=0)
    total_displacement_minutes: int = Field(ge=0)
    makespan_minutes: int = Field(ge=0)
    weighted_value: float = Field(ge=0)


class PreparationRepairDiagnostics(StrictRepairModel):
    strategy: PreparationRepairStrategy
    deterministic: bool = True
    explored_states: int = Field(default=0, ge=0)
    pruned_states: int = Field(default=0, ge=0)
    candidate_placements_considered: int = Field(default=0, ge=0)
    preserved_attempt_count: int = Field(default=0, ge=0)
    exact_search_truncated: bool = False
    tie_break_rule: str
    limitations: List[str] = Field(default_factory=list)


class PreparationScheduleRepairResult(StrictRepairModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "required": [
                "response",
                "complete",
                "immutable_task_ids",
                "preserved_task_ids",
                "moved_tasks",
                "added_task_ids",
                "removed_task_ids",
                "unscheduled_task_ids",
                "objective",
                "diagnostics",
                "warnings",
                "previous_schedule_hash",
                "revised_request_hash",
                "repaired_response_hash",
                "requires_human_acceptance",
                "accepted",
                "persistence_performed",
            ]
        },
    )

    response: PreparationScheduleResponse
    complete: bool
    immutable_task_ids: List[str]
    preserved_task_ids: List[str]
    moved_tasks: List[PreparationTaskMovement]
    added_task_ids: List[str]
    removed_task_ids: List[str]
    unscheduled_task_ids: List[str]
    objective: PreparationRepairObjective
    diagnostics: PreparationRepairDiagnostics
    warnings: List[str] = Field(default_factory=list)
    previous_schedule_hash: Optional[str] = None
    revised_request_hash: Optional[str] = None
    repaired_response_hash: Optional[str] = None
    requires_human_acceptance: bool = True
    accepted: bool = False
    persistence_performed: bool = False

    @model_validator(mode="after")
    def validate_partition(self):
        groups = [
            set(self.preserved_task_ids),
            {value.task_id for value in self.moved_tasks},
            set(self.added_task_ids),
            set(self.unscheduled_task_ids),
        ]
        for index, left in enumerate(groups):
            for right in groups[index + 1 :]:
                if left & right:
                    raise ValueError("repair task outcome groups must be disjoint")
        if self.complete != (len(self.unscheduled_task_ids) == 0):
            raise ValueError("complete must match unscheduled task outcome")
        if not self.requires_human_acceptance:
            raise ValueError("repair results must require explicit human acceptance")
        if self.accepted:
            raise ValueError("repair computation cannot mark a result accepted")
        if self.persistence_performed:
            raise ValueError("repair computation cannot persist a result")
        return self


class PreparationRepairBenchmarkCase(StrictRepairModel):
    case_id: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    request: PreparationScheduleRepairRequest
    expected_complete: bool
    maximum_changed_tasks: Optional[int] = Field(default=None, ge=0)
    maximum_total_displacement_minutes: Optional[int] = Field(default=None, ge=0)
    required_preserved_task_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class PreparationRepairBenchmarkReport(StrictRepairModel):
    case_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_case_ids: List[str] = Field(default_factory=list)
    results: Dict[str, PreparationScheduleRepairResult] = Field(default_factory=dict)
