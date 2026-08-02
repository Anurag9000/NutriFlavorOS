"""Contracts for immutable, server-recomputed preparation repair proposals.

Proposal computation remains advisory. A separate acceptance action may create
one new draft after exact acknowledgement and method-aware replay. Acceptance
never approves, executes, completes, or mutates the source schedule.
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
from backend.domain.preparation_schedule_replay import REPAIR_SCHEDULER_METHOD


class PreparationRepairProposalStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"


class PreparationRepairProposalEventType(str, Enum):
    CREATED = "created"
    ACCEPTED = "accepted"
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


class PreparationRepairProposalInvalidateRequest(StrictRepairModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)
    acknowledge_historical_only: Literal[True]
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


class PreparationRepairProposalAcceptRequest(StrictRepairModel):
    expected_proposal_version: int = Field(ge=1)
    expected_source_schedule_version: int = Field(ge=1)
    expected_source_schedule_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    expected_source_schedule_request_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    expected_target_calendar_content_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    expected_repair_request_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    expected_repair_result_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    expected_revised_request_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    expected_repaired_response_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    acknowledged_task_ids: List[str] = Field(max_length=10_000)
    reason: str = Field(min_length=1, max_length=4000)
    acknowledge_creates_new_draft_only: Literal[True]
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self):
        identifiers = [value.strip() for value in self.acknowledged_task_ids]
        if any(not value for value in identifiers):
            raise ValueError("acknowledged task IDs cannot be blank")
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("acknowledged task IDs must be unique")
        self.acknowledged_task_ids = sorted(identifiers)
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
    accepted: bool
    schedule_persistence_performed: bool
    accepted_schedule_id: Optional[int]
    accepted_schedule_hash: Optional[str]
    accepted_by_user_id: Optional[str]
    accepted_at: Optional[str]
    acceptance_reason: Optional[str]
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def validate_acceptance_state(self):
        accepted_fields = [
            self.accepted_schedule_id,
            self.accepted_schedule_hash,
            self.accepted_by_user_id,
            self.accepted_at,
            self.acceptance_reason,
        ]
        if self.status == PreparationRepairProposalStatus.ACCEPTED:
            if not self.accepted or not self.schedule_persistence_performed:
                raise ValueError("accepted proposal must report draft persistence")
            if any(value is None for value in accepted_fields):
                raise ValueError("accepted proposal requires complete acceptance evidence")
        else:
            if self.accepted or self.schedule_persistence_performed:
                raise ValueError("non-accepted proposal cannot report draft persistence")
            if any(value is not None for value in accepted_fields):
                raise ValueError("non-accepted proposal cannot expose acceptance evidence")
        return self


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


class PreparationRepairProposalAcceptanceView(StrictRepairModel):
    id: int
    household_id: str
    proposal_id: int
    proposal_version_before: int
    proposal_version_after: int
    source_schedule_id: int
    source_schedule_version: int
    created_schedule_id: int
    created_schedule_version: Literal[1]
    created_schedule_status: Literal["draft"]
    created_schedule_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    derivation_method: Literal[
        "deterministic_minimal_change_preparation_repair_v1"
    ] = REPAIR_SCHEDULER_METHOD
    source_schedule_hash: str
    source_schedule_request_hash: str
    target_calendar_content_hash: str
    repair_request_hash: str
    repair_result_hash: str
    revised_request_hash: str
    repaired_response_hash: str
    acknowledged_task_ids: List[str]
    reason: str
    actor_user_id: str
    metadata: Dict[str, Any]
    idempotency_key: str
    request_fingerprint: str
    created_at: str


class PreparationRepairProposalAcceptedDraftView(StrictRepairModel):
    proposal: PreparationRepairProposalView
    acceptance: PreparationRepairProposalAcceptanceView
    accepted: Literal[True]
    schedule_persistence_performed: Literal[True]
    approval_performed: Literal[False]
    execution_performed: Literal[False]
