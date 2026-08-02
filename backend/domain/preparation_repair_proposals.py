"""Contracts for immutable, server-recomputed preparation repair proposals.

A proposal is persisted review evidence, not an accepted or executable schedule.
It never changes the source schedule and cannot be approved or executed.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair import (
    PreparationRepairStrategy,
    PreparationRepairWeights,
    PreparationScheduleRepairResult,
    StrictRepairModel,
)


class PreparationRepairProposalStatus(str, Enum):
    PROPOSED = "proposed"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"


class PreparationRepairProposalEventType(str, Enum):
    CREATED = "created"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"


class PreparationRepairProposalCreateRequest(StrictRepairModel):
    source_schedule_id: int = Field(ge=1)
    expected_source_version: int = Field(ge=1)
    target_calendar_version_id: int = Field(ge=1)
    revised_request: PreparationScheduleRequest
    immutable_task_ids: List[str] = Field(default_factory=list, max_length=10_000)
    strategy: PreparationRepairStrategy = PreparationRepairStrategy.GREEDY_MIN_CHANGE
    weights: PreparationRepairWeights = Field(default_factory=PreparationRepairWeights)
    exact_task_limit: int = Field(default=9, ge=1, le=12)
    exact_candidate_limit_per_task: int = Field(default=80, ge=1, le=500)
    notes: Optional[str] = Field(default=None, max_length=4000)
    acknowledge_non_acceptance: Literal[True]
    acknowledge_non_persistence: Literal[True]
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )

    @model_validator(mode="after")
    def normalize(self):
        normalized = [value.strip() for value in self.immutable_task_ids]
        if any(not value for value in normalized):
            raise ValueError("immutable task IDs cannot be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("immutable task IDs must be unique")
        self.immutable_task_ids = sorted(normalized)
        self.notes = self.notes.strip() if self.notes else None
        return self


class PreparationRepairProposalRejectRequest(StrictRepairModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self):
        self.reason = " ".join(self.reason.strip().split())
        if not self.reason:
            raise ValueError("reason cannot be blank")
        return self


class PreparationRepairProposalView(StrictRepairModel):
    id: int
    household_id: str
    source_schedule_id: int
    source_schedule_version: int
    source_schedule_hash: str
    source_schedule_request_hash: str
    target_calendar_version_id: int
    target_calendar_content_hash: str
    repair_request_hash: str
    repair_result_hash: str
    revised_request_hash: str
    repaired_response_hash: str
    required_acknowledgement_task_ids: List[str]
    repair_result: PreparationScheduleRepairResult
    status: PreparationRepairProposalStatus
    version: int
    notes: Optional[str]
    created_by_user_id: str
    rejected_by_user_id: Optional[str]
    rejected_at: Optional[str]
    rejection_reason: Optional[str]
    current: bool
    stale_reasons: List[str]
    accepted: Literal[False] = False
    schedule_persistence_performed: Literal[False] = False
    created_at: str
    updated_at: str


class PreparationRepairProposalEventView(StrictRepairModel):
    id: int
    proposal_id: int
    household_id: str
    event_type: PreparationRepairProposalEventType
    actor_user_id: str
    from_status: Optional[PreparationRepairProposalStatus]
    to_status: PreparationRepairProposalStatus
    reason: str
    metadata: Dict[str, Any]
    proposal_version_before: int
    proposal_version_after: int
    idempotency_key: str
    request_fingerprint: str
    created_at: str
