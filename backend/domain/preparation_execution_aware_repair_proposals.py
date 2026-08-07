"""Fail-closed contracts for execution-aware preparation repair preflight.

This boundary is intentionally separate from ordinary repair. It binds a future
repair request to exact execution evidence and can normalize only work that has
not started. It does not persist a proposal, create a schedule, approve work, or
record execution.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import Field, model_validator

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair import (
    PreparationRepairStrategy,
    PreparationRepairWeights,
    StrictRepairModel,
)


_SHA256_PATTERN = r"^[a-f0-9]{64}$"


class PreparationExecutionAwareRepairProposalCreateRequest(StrictRepairModel):
    """First-class request identity for a future execution-aware proposal.

    ``revised_request`` is a full source-shaped request at this phase. Task IDs
    may not be added or removed yet; only tasks proven ``repairable`` by the exact
    execution snapshot may differ from their source definitions. This keeps the
    first mutation boundary conservative while provenance for introduced or
    removed tasks remains future work.
    """

    source_schedule_id: int = Field(ge=1)
    expected_source_version: int = Field(ge=1)
    expected_source_schedule_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )
    expected_execution_snapshot_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )
    expected_execution_aware_snapshot_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )
    target_calendar_version_id: int = Field(ge=1)
    revised_request: PreparationScheduleRequest
    strategy: PreparationRepairStrategy = PreparationRepairStrategy.GREEDY_MIN_CHANGE
    weights: PreparationRepairWeights = Field(default_factory=PreparationRepairWeights)
    exact_task_limit: int = Field(default=9, ge=1, le=12)
    exact_candidate_limit_per_task: int = Field(default=80, ge=1, le=500)
    notes: Optional[str] = Field(default=None, max_length=4000)
    acknowledge_execution_history_immutable: Literal[True]
    acknowledge_in_progress_work_not_moved: Literal[True]
    acknowledge_preflight_only: Literal[True]
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )

    @model_validator(mode="after")
    def normalize(self):
        self.notes = self.notes.strip() if self.notes else None
        return self


class PreparationExecutionAwareRepairPreflightView(StrictRepairModel):
    source_schedule_id: int = Field(ge=1)
    source_schedule_version: int = Field(ge=1)
    source_schedule_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )
    canonical_execution_snapshot_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )
    execution_aware_snapshot_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=_SHA256_PATTERN,
    )
    target_calendar_version_id: int = Field(ge=1)
    frozen_task_ids: List[str]
    terminal_task_ids: List[str]
    in_progress_task_ids: List[str]
    repairable_task_ids: List[str]
    blocked_by_in_progress_task_ids: Dict[str, List[str]]
    candidate_task_ids: List[str]
    normalized_future_request: PreparationScheduleRequest
    ready_for_proposal_computation: bool
    requires_human_acceptance: Literal[True]
    repair_computation_performed: Literal[False]
    proposal_persistence_performed: Literal[False]
    schedule_persistence_performed: Literal[False]
    limitations: List[str]

    @model_validator(mode="after")
    def validate_partitions(self):
        frozen = set(self.frozen_task_ids)
        terminal = set(self.terminal_task_ids)
        active = set(self.in_progress_task_ids)
        repairable = set(self.repairable_task_ids)
        blocked = set(self.blocked_by_in_progress_task_ids)
        candidates = set(self.candidate_task_ids)
        normalized_ids = {
            task.task_id for task in self.normalized_future_request.tasks
        }

        if terminal | active != frozen:
            raise ValueError("terminal and in-progress tasks must form frozen frontier")
        if frozen & repairable:
            raise ValueError("frozen and repairable task IDs must be disjoint")
        if blocked - repairable:
            raise ValueError("only repairable tasks can be blocked by in-progress work")
        if candidates != repairable - blocked:
            raise ValueError("candidate tasks must be exactly unblocked repairable tasks")
        if normalized_ids != candidates:
            raise ValueError("normalized future request must contain exactly candidate tasks")
        for task_id, blockers in self.blocked_by_in_progress_task_ids.items():
            if not blockers or any(value not in active for value in blockers):
                raise ValueError(
                    f"blocked task {task_id} must identify in-progress ancestors"
                )
        if self.ready_for_proposal_computation != bool(candidates):
            raise ValueError("preflight readiness must match candidate frontier")
        if not self.limitations:
            raise ValueError("execution-aware preflight must state limitations")
        return self


__all__ = [
    "PreparationExecutionAwareRepairPreflightView",
    "PreparationExecutionAwareRepairProposalCreateRequest",
]
