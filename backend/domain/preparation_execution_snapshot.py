"""Canonical execution-state identity for execution-aware preparation repair.

The snapshot separates audit time from semantic identity. Its content hash binds
the exact source schedule version, ordered append-only execution ledger, task
states, and frozen/repairable/in-progress sets. Re-reading the same execution
state later therefore produces the same identity even though ``captured_at``
changes.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import List, Literal, Optional

from pydantic import Field, model_validator

from backend.domain.preparation_operations import StrictPreparationOperationsModel
from backend.domain.preparation_task_execution import PreparationTaskExecutionState


EXECUTION_SNAPSHOT_VERSION = "preparation-execution-snapshot-v1"


class PreparationRepairTaskLineageStatus(str, Enum):
    """Relationship between a source task and an execution-aware replacement."""

    PRESERVED = "preserved"
    FROZEN_BY_EXECUTION = "frozen_by_execution"
    SHIFTED = "shifted"
    NEWLY_INTRODUCED = "newly_introduced"
    REMOVED_BEFORE_EXECUTION = "removed_before_execution"
    BLOCKED_BY_IN_PROGRESS_PREDECESSOR = "blocked_by_in_progress_predecessor"
    SUPERSEDED_BY_REPLACEMENT = "superseded_by_replacement"


class PreparationExecutionTaskSnapshot(StrictPreparationOperationsModel):
    task_id: str = Field(min_length=1, max_length=160)
    state: PreparationTaskExecutionState
    # Required-but-nullable: every serialized task snapshot carries the key, and
    # ``null`` is meaningful proof that the task is still planned.
    latest_event_id: Optional[int] = Field(ge=1)

    @model_validator(mode="after")
    def validate_event_identity(self):
        if self.state == PreparationTaskExecutionState.PLANNED:
            if self.latest_event_id is not None:
                raise ValueError("planned execution snapshot task cannot have an event ID")
        elif self.latest_event_id is None:
            raise ValueError("non-planned execution snapshot task requires an event ID")
        return self


class PreparationExecutionSnapshot(StrictPreparationOperationsModel):
    # Required literal discriminator: generated clients must receive the exact
    # snapshot contract version rather than treating it as an optional default.
    snapshot_version: Literal["preparation-execution-snapshot-v1"]
    source_schedule_id: int = Field(ge=1)
    source_schedule_version: int = Field(ge=1)
    # Required-but-nullable so generated clients distinguish an empty ledger from
    # an omitted/unknown identity field.
    latest_execution_event_id: Optional[int] = Field(ge=1)
    execution_event_count: int = Field(ge=0)
    execution_event_ledger_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    task_states: List[PreparationExecutionTaskSnapshot]
    frozen_task_ids: List[str]
    repairable_task_ids: List[str]
    in_progress_task_ids: List[str]
    captured_at: str = Field(min_length=1, max_length=80)
    execution_snapshot_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )

    @model_validator(mode="after")
    def validate_partition_and_identity(self):
        task_ids = [value.task_id for value in self.task_states]
        if task_ids != sorted(task_ids) or len(task_ids) != len(set(task_ids)):
            raise ValueError("execution snapshot task states must be unique and sorted")

        expected_frozen = sorted(
            value.task_id
            for value in self.task_states
            if value.state
            in {
                PreparationTaskExecutionState.COMPLETED,
                PreparationTaskExecutionState.SKIPPED,
            }
        )
        expected_repairable = sorted(
            value.task_id
            for value in self.task_states
            if value.state == PreparationTaskExecutionState.PLANNED
        )
        expected_in_progress = sorted(
            value.task_id
            for value in self.task_states
            if value.state == PreparationTaskExecutionState.IN_PROGRESS
        )
        if self.frozen_task_ids != expected_frozen:
            raise ValueError("frozen task IDs disagree with terminal execution states")
        if self.repairable_task_ids != expected_repairable:
            raise ValueError("repairable task IDs disagree with planned execution states")
        if self.in_progress_task_ids != expected_in_progress:
            raise ValueError("in-progress task IDs disagree with execution states")

        if self.execution_event_count == 0:
            if self.latest_execution_event_id is not None:
                raise ValueError("empty execution ledger cannot have a latest event ID")
            if any(value.latest_event_id is not None for value in self.task_states):
                raise ValueError("empty execution ledger cannot have task event IDs")
        elif self.latest_execution_event_id is None:
            raise ValueError("non-empty execution ledger requires a latest event ID")

        expected_hash = preparation_execution_snapshot_hash(self)
        if self.execution_snapshot_hash != expected_hash:
            raise ValueError("execution snapshot hash disagrees with semantic identity")
        return self


def preparation_execution_snapshot_identity_payload(
    snapshot: PreparationExecutionSnapshot,
) -> dict:
    """Return semantic identity material, deliberately excluding capture time."""

    return {
        "snapshot_version": snapshot.snapshot_version,
        "source_schedule_id": snapshot.source_schedule_id,
        "source_schedule_version": snapshot.source_schedule_version,
        "latest_execution_event_id": snapshot.latest_execution_event_id,
        "execution_event_count": snapshot.execution_event_count,
        "execution_event_ledger_hash": snapshot.execution_event_ledger_hash,
        "task_states": [
            value.model_dump(mode="json") for value in snapshot.task_states
        ],
        "frozen_task_ids": snapshot.frozen_task_ids,
        "repairable_task_ids": snapshot.repairable_task_ids,
        "in_progress_task_ids": snapshot.in_progress_task_ids,
    }


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def preparation_execution_snapshot_hash(
    snapshot: PreparationExecutionSnapshot,
) -> str:
    """Hash the semantic execution identity without its audit capture time/hash."""

    return _canonical_hash(preparation_execution_snapshot_identity_payload(snapshot))


def execution_event_ledger_hash(events: list[dict]) -> str:
    """Hash an already ordered append-only execution-event ledger."""

    return _canonical_hash(events)


__all__ = [
    "EXECUTION_SNAPSHOT_VERSION",
    "PreparationExecutionSnapshot",
    "PreparationExecutionTaskSnapshot",
    "PreparationRepairTaskLineageStatus",
    "execution_event_ledger_hash",
    "preparation_execution_snapshot_hash",
    "preparation_execution_snapshot_identity_payload",
]
