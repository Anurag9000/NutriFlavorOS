"""Immutable evidence contracts for execution-aware preparation repair.

These models describe the authoritative boundary between already-confirmed work
and work that remains eligible for future repair. They do not compute, persist,
approve, or execute a replacement schedule.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import Field, model_validator

from backend.domain.preparation_repair import StrictRepairModel
from backend.domain.preparation_task_execution import PreparationTaskExecutionState


class PreparationExecutionAwareTaskEvidence(StrictRepairModel):
    task_id: str = Field(min_length=1, max_length=160)
    state: PreparationTaskExecutionState
    planned_start_minute: int = Field(ge=0, le=10080)
    planned_finish_minute: int = Field(gt=0, le=10080)
    dependencies: List[str]
    latest_event_id: Optional[int] = Field(default=None, ge=1)
    confirmed_start_minute: Optional[int] = Field(default=None, ge=0, le=10080)
    confirmed_terminal_minute: Optional[int] = Field(default=None, ge=0, le=10080)
    terminal_event_type: Optional[Literal["completed", "skipped"]] = None
    terminal_reason: Optional[str] = Field(default=None, max_length=1000)
    frozen: bool
    terminal: bool
    repairable: bool

    @model_validator(mode="after")
    def validate_state_evidence(self):
        if self.planned_finish_minute <= self.planned_start_minute:
            raise ValueError("planned finish must be after planned start")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("task dependencies must be unique")
        if self.state == PreparationTaskExecutionState.PLANNED:
            if self.frozen or self.terminal or not self.repairable:
                raise ValueError("planned task must remain repairable and unfrozen")
            if any(
                value is not None
                for value in (
                    self.latest_event_id,
                    self.confirmed_start_minute,
                    self.confirmed_terminal_minute,
                    self.terminal_event_type,
                    self.terminal_reason,
                )
            ):
                raise ValueError("planned task cannot expose execution evidence")
        elif self.state == PreparationTaskExecutionState.IN_PROGRESS:
            if not self.frozen or self.terminal or self.repairable:
                raise ValueError("in-progress task must be frozen and nonterminal")
            if self.latest_event_id is None or self.confirmed_start_minute is None:
                raise ValueError("in-progress task requires confirmed start evidence")
            if any(
                value is not None
                for value in (
                    self.confirmed_terminal_minute,
                    self.terminal_event_type,
                    self.terminal_reason,
                )
            ):
                raise ValueError("in-progress task cannot expose terminal evidence")
        else:
            if not self.frozen or not self.terminal or self.repairable:
                raise ValueError("terminal task must be frozen and non-repairable")
            if self.latest_event_id is None or self.confirmed_terminal_minute is None:
                raise ValueError("terminal task requires terminal event evidence")
            expected = (
                "completed"
                if self.state == PreparationTaskExecutionState.COMPLETED
                else "skipped"
            )
            if self.terminal_event_type != expected:
                raise ValueError("terminal event type must match terminal task state")
            if (
                self.confirmed_start_minute is not None
                and self.confirmed_terminal_minute < self.confirmed_start_minute
            ):
                raise ValueError("terminal minute cannot precede confirmed start")
        return self


class PreparationExecutionAwareRepairSnapshot(StrictRepairModel):
    household_id: str = Field(min_length=1, max_length=160)
    source_schedule_id: int = Field(ge=1)
    source_schedule_version: int = Field(ge=1)
    source_schedule_status: str = Field(min_length=1, max_length=32)
    source_schedule_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    # Cryptographically binds this richer execution-aware projection to the
    # canonical mutation-authority snapshot used by proposal creation/acceptance.
    canonical_execution_snapshot_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    event_count: int = Field(ge=0)
    event_ids: List[int]
    first_event_schedule_version: Optional[int] = Field(default=None, ge=1)
    latest_event_schedule_version: Optional[int] = Field(default=None, ge=1)
    event_chain_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    tasks: List[PreparationExecutionAwareTaskEvidence]
    frozen_task_ids: List[str]
    active_task_ids: List[str]
    terminal_task_ids: List[str]
    satisfied_dependency_task_ids: List[str]
    repairable_task_ids: List[str]
    ready_repairable_task_ids: List[str]
    blocked_repairable_tasks: Dict[str, List[str]]
    snapshot_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    requires_human_acceptance: Literal[True]
    repair_computation_performed: Literal[False]
    persistence_performed: Literal[False]
    limitations: List[str]

    @model_validator(mode="after")
    def validate_partitions(self):
        task_ids = [value.task_id for value in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("execution-aware task IDs must be unique")
        if self.event_count != len(self.event_ids):
            raise ValueError("event count must match event IDs")
        if len(self.event_ids) != len(set(self.event_ids)):
            raise ValueError("event IDs must be unique")
        if self.event_count == 0:
            if (
                self.first_event_schedule_version is not None
                or self.latest_event_schedule_version is not None
            ):
                raise ValueError("empty event chain cannot expose event versions")
        elif (
            self.first_event_schedule_version is None
            or self.latest_event_schedule_version is None
            or self.latest_event_schedule_version < self.first_event_schedule_version
        ):
            raise ValueError("nonempty event chain requires an ordered version range")

        frozen = {value.task_id for value in self.tasks if value.frozen}
        active = {
            value.task_id
            for value in self.tasks
            if value.state == PreparationTaskExecutionState.IN_PROGRESS
        }
        terminal = {value.task_id for value in self.tasks if value.terminal}
        repairable = {value.task_id for value in self.tasks if value.repairable}
        if frozen != set(self.frozen_task_ids):
            raise ValueError("frozen task partition differs from task evidence")
        if active != set(self.active_task_ids):
            raise ValueError("active task partition differs from task evidence")
        if terminal != set(self.terminal_task_ids):
            raise ValueError("terminal task partition differs from task evidence")
        if terminal != set(self.satisfied_dependency_task_ids):
            raise ValueError("terminal tasks are the satisfied dependency frontier")
        if repairable != set(self.repairable_task_ids):
            raise ValueError("repairable task partition differs from task evidence")
        if frozen & repairable:
            raise ValueError("frozen and repairable tasks must be disjoint")
        if frozen | repairable != set(task_ids):
            raise ValueError("frozen and repairable tasks must partition all tasks")

        blocked = set(self.blocked_repairable_tasks)
        ready = set(self.ready_repairable_task_ids)
        if blocked & ready or blocked | ready != repairable:
            raise ValueError("ready and blocked tasks must partition repairable tasks")
        for task_id, blockers in self.blocked_repairable_tasks.items():
            if task_id not in repairable or not blockers:
                raise ValueError("blocked repairable task requires nonterminal blockers")
            if any(value not in set(task_ids) - terminal for value in blockers):
                raise ValueError("blocked task references a terminal or unknown blocker")
        if not self.limitations:
            raise ValueError("execution-aware snapshot must state its limitations")
        return self
