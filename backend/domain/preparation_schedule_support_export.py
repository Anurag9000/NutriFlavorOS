"""Strict read-only support export for one persisted preparation schedule."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import Field, model_validator

from backend.domain.preparation_operations import (
    PersistedPreparationScheduleView,
    PreparationScheduleEventView,
    StrictPreparationOperationsModel,
)
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptanceView,
    PreparationRepairProposalEventView,
    PreparationRepairProposalView,
)
from backend.domain.preparation_schedule_derivation import (
    PreparationScheduleDerivationEvidenceView,
)
from backend.domain.preparation_task_execution import (
    PreparationTaskExecutionOverview,
)
from backend.domain.preparation_task_execution_eligibility import (
    PreparationTaskExecutionEligibilityView,
)


class PreparationScheduleSupportExport(StrictPreparationOperationsModel):
    document_version: Literal["preparation-schedule-support-export-v1"]
    household_id: str
    schedule_id: int = Field(ge=1)
    database_dialect: str
    snapshot_isolation: Literal["repeatable_read", "serializable"]
    snapshot_read_only: Literal[True]
    snapshot_marker: Optional[str]
    snapshot_started_at: str
    snapshot_completed_at: str

    schedule: PersistedPreparationScheduleView
    schedule_events: List[PreparationScheduleEventView]
    derivation: PreparationScheduleDerivationEvidenceView
    task_execution_eligibility: PreparationTaskExecutionEligibilityView
    task_execution: PreparationTaskExecutionOverview

    related_repair_proposals: List[PreparationRepairProposalView]
    repair_acceptances: List[PreparationRepairProposalAcceptanceView]
    repair_proposal_events: Dict[str, List[PreparationRepairProposalEventView]]

    evidence_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    mutation_performed: Literal[False]
    actual_execution_verified: Literal[False]
    food_safety_verified: Literal[False]

    @model_validator(mode="after")
    def validate_cross_record_identity(self):
        if self.household_id != self.schedule.household_id:
            raise ValueError("export household must match schedule household")
        if self.schedule_id != self.schedule.id:
            raise ValueError("export schedule ID must match schedule evidence")

        schedule_views = [
            (
                self.derivation.household_id,
                self.derivation.schedule_id,
                self.derivation.schedule_version,
                self.derivation.schedule_status,
            ),
            (
                self.task_execution_eligibility.household_id,
                self.task_execution_eligibility.schedule_id,
                self.task_execution_eligibility.schedule_version,
                self.task_execution_eligibility.schedule_status,
            ),
            (
                self.task_execution.schedule.household_id,
                self.task_execution.schedule.id,
                self.task_execution.schedule.version,
                self.task_execution.schedule.status.value,
            ),
        ]
        expected = (
            self.schedule.household_id,
            self.schedule.id,
            self.schedule.version,
            self.schedule.status.value,
        )
        if any(value != expected for value in schedule_views):
            raise ValueError("support export schedule views are not snapshot-consistent")
        if any(
            value.schedule_id != self.schedule_id
            or value.household_id != self.household_id
            for value in self.schedule_events
        ):
            raise ValueError("schedule event is outside the exported schedule")

        proposal_ids = [value.id for value in self.related_repair_proposals]
        if proposal_ids != sorted(set(proposal_ids)):
            raise ValueError("related proposal IDs must be unique and ordered")
        if any(
            value.household_id != self.household_id
            for value in self.related_repair_proposals
        ):
            raise ValueError("related proposal is outside the exported household")

        proposal_id_set = set(proposal_ids)
        if any(
            value.household_id != self.household_id
            or value.proposal_id not in proposal_id_set
            for value in self.repair_acceptances
        ):
            raise ValueError("repair acceptance is outside the related proposal set")
        if set(self.repair_proposal_events) != {
            str(value) for value in proposal_ids
        }:
            raise ValueError("proposal event map must cover every related proposal")
        for key, events in self.repair_proposal_events.items():
            proposal_id = int(key)
            if any(
                value.proposal_id != proposal_id
                or value.household_id != self.household_id
                for value in events
            ):
                raise ValueError("proposal event is outside its related proposal")

        derivation_proposal_id = self.derivation.source_repair_proposal_id
        if (
            derivation_proposal_id is not None
            and derivation_proposal_id not in proposal_id_set
        ):
            raise ValueError("repair derivation proposal is absent from export")
        eligibility_proposal_id = (
            self.task_execution_eligibility.accepted_proposal_id
        )
        if (
            eligibility_proposal_id is not None
            and eligibility_proposal_id not in proposal_id_set
        ):
            raise ValueError("accepted replacement proposal is absent from export")
        return self


__all__ = ["PreparationScheduleSupportExport"]
