"""Strict contracts for deterministic method-aware preparation replay.

Original scheduler output and minimal-change repair output are different
algorithms with different authoritative inputs. A persisted or proposed result
must identify its derivation method explicitly; replay never guesses a method
from the shape of a response.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import Field, model_validator

from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_repair import (
    PreparationScheduleRepairRequest,
    PreparationScheduleRepairResult,
    StrictRepairModel,
)


ORIGINAL_SCHEDULER_METHOD = (
    "deterministic_dependency_aware_resource_scheduler_v2"
)
REPAIR_SCHEDULER_METHOD = (
    "deterministic_minimal_change_preparation_repair_v1"
)


class PreparationScheduleDerivationMethod(str, Enum):
    ORIGINAL = ORIGINAL_SCHEDULER_METHOD
    REPAIR = REPAIR_SCHEDULER_METHOD


class OriginalPreparationScheduleReplay(StrictRepairModel):
    method: Literal[
        "deterministic_dependency_aware_resource_scheduler_v2"
    ] = ORIGINAL_SCHEDULER_METHOD
    request: PreparationScheduleRequest
    expected_response: PreparationScheduleResponse
    expected_request_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    expected_response_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )

    @model_validator(mode="after")
    def validate_method_identity(self):
        if self.expected_response.method != self.method:
            raise ValueError(
                "original replay response method must equal the original scheduler method"
            )
        if not self.expected_response.deterministic:
            raise ValueError("original replay response must be deterministic")
        if self.expected_response.unscheduled:
            raise ValueError("original persisted replay must be complete")
        return self


class RepairedPreparationScheduleReplay(StrictRepairModel):
    method: Literal[
        "deterministic_minimal_change_preparation_repair_v1"
    ] = REPAIR_SCHEDULER_METHOD
    repair_request: PreparationScheduleRepairRequest
    expected_result: PreparationScheduleRepairResult
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
    expected_response_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )

    @model_validator(mode="after")
    def validate_method_identity(self):
        if self.expected_result.response.method != self.method:
            raise ValueError(
                "repair replay response method must equal the repair method"
            )
        if not self.expected_result.response.deterministic:
            raise ValueError("repair replay response must be deterministic")
        if not self.expected_result.complete:
            raise ValueError("persistable repair replay must be complete")
        if self.expected_result.unscheduled_task_ids:
            raise ValueError("persistable repair replay cannot contain unresolved tasks")
        if self.expected_result.response.unscheduled:
            raise ValueError("persistable repair response cannot contain unresolved tasks")
        if not self.expected_result.requires_human_acceptance:
            raise ValueError("repair replay must retain the human-acceptance boundary")
        if self.expected_result.accepted:
            raise ValueError("repair computation cannot be pre-marked accepted")
        if self.expected_result.persistence_performed:
            raise ValueError("repair computation cannot claim persistence")
        if (
            self.expected_result.revised_request_hash
            != self.expected_revised_request_hash
        ):
            raise ValueError("repair result revised-request hash differs from envelope")
        if self.expected_result.repaired_response_hash != self.expected_response_hash:
            raise ValueError("repair result response hash differs from envelope")
        return self


class PreparationScheduleReplayEvidence(StrictRepairModel):
    method: PreparationScheduleDerivationMethod
    deterministic: Literal[True]
    request_hash: str
    response_hash: str
    result_hash: Optional[str] = None
    replayed_response: PreparationScheduleResponse
