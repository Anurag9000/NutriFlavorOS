"""Runtime mutation contracts for persisted preparation operations.

Persisted schedules carry the complete reviewed occurrence set, deterministic
request, and response. The service verifies provenance and replays the scheduler
before accepting or approving a schedule.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from pydantic import Field, model_validator

from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_evidence import DurationPolicy
from backend.domain.preparation_operations import (
    PreparationOccurrenceSetDocument,
    StrictPreparationOperationsModel,
)


PROFILE_HASH_PATTERN = re.compile(r"(?:^|/)sha256:([a-f0-9]{64})$")


class PersistedScheduleCreateRequest(StrictPreparationOperationsModel):
    calendar_version_id: int = Field(ge=1)
    source_plan_id: Optional[int] = Field(default=None, ge=1)
    source_plan_version: Optional[int] = Field(default=None, ge=1)
    occurrence_set: PreparationOccurrenceSetDocument
    profile_versions: Dict[str, str] = Field(default_factory=dict, max_length=1000)
    schedule_request: PreparationScheduleRequest
    schedule_response: PreparationScheduleResponse
    notes: Optional[str] = Field(default=None, max_length=4000)
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )

    @model_validator(mode="after")
    def validate_source_versions(self):
        if (self.source_plan_id is None) != (self.source_plan_version is None):
            raise ValueError(
                "source_plan_id and source_plan_version must be supplied together"
            )
        if self.schedule_response.unscheduled:
            raise ValueError("persisted schedules must be complete")
        if self.schedule_request.horizon_minutes != self.schedule_response.horizon_minutes:
            raise ValueError("schedule request and response horizons differ")
        if self.schedule_request.granularity_minutes != self.schedule_response.granularity_minutes:
            raise ValueError("schedule request and response granularity differs")

        normalized: Dict[str, str] = {}
        profile_hashes: set[str] = set()
        for raw_key, raw_value in self.profile_versions.items():
            key = raw_key.strip()
            value = raw_value.strip()
            if not key or not value:
                raise ValueError("profile_versions keys and values cannot be blank")
            match = PROFILE_HASH_PATTERN.search(value)
            if match is None:
                raise ValueError(
                    "profile_versions values must end with a lowercase sha256 digest"
                )
            normalized[key] = value
            profile_hashes.add(match.group(1))
        self.profile_versions = dict(sorted(normalized.items()))

        occurrences = {
            value.occurrence_id: value for value in self.occurrence_set.occurrences
        }
        outside = sorted(
            value.occurrence_id
            for value in occurrences.values()
            if value.required_finish_minute > self.schedule_request.horizon_minutes
        )
        if outside:
            raise ValueError(
                "occurrence finish times exceed the scheduling horizon: "
                + ", ".join(outside)
            )

        observed_occurrences: set[str] = set()
        task_hashes: set[str] = set()
        for task in self.schedule_request.tasks:
            metadata = task.metadata
            occurrence_id = str(metadata.get("occurrence_id") or "")
            occurrence = occurrences.get(occurrence_id)
            if occurrence is None:
                raise ValueError(
                    f"task {task.task_id} references an unknown occurrence_id"
                )
            observed_occurrences.add(occurrence_id)
            if metadata.get("recipe_id") != occurrence.recipe_id:
                raise ValueError(
                    f"task {task.task_id} recipe_id differs from its occurrence"
                )
            if float(metadata.get("servings", -1)) != occurrence.servings:
                raise ValueError(
                    f"task {task.task_id} servings differ from its occurrence"
                )
            if task.priority != occurrence.priority:
                raise ValueError(
                    f"task {task.task_id} priority differs from its occurrence"
                )
            if task.latest_finish_minute != occurrence.required_finish_minute:
                raise ValueError(
                    f"task {task.task_id} deadline differs from its occurrence"
                )

            profile_hash = str(metadata.get("profile_content_hash") or "")
            if len(profile_hash) != 64 or any(
                character not in "0123456789abcdef" for character in profile_hash
            ):
                raise ValueError(
                    "task profile_content_hash values must be lowercase SHA-256 digests"
                )
            task_hashes.add(profile_hash)

            minimum = metadata.get("duration_min_minutes")
            maximum = metadata.get("duration_max_minutes")
            if not isinstance(minimum, int) or not isinstance(maximum, int):
                raise ValueError(
                    f"task {task.task_id} lacks reviewed duration interval provenance"
                )
            expected_duration = (
                maximum
                if self.occurrence_set.duration_policy
                == DurationPolicy.CONSERVATIVE_MAX
                else minimum
            )
            if task.duration_minutes != expected_duration:
                raise ValueError(
                    f"task {task.task_id} duration differs from occurrence-set duration policy"
                )

        missing_occurrences = sorted(set(occurrences) - observed_occurrences)
        if missing_occurrences:
            raise ValueError(
                "occurrence set contains occurrences without compiled tasks: "
                + ", ".join(missing_occurrences)
            )
        if profile_hashes != task_hashes:
            raise ValueError(
                "profile_versions hashes must exactly match task profile_content_hash values"
            )
        if set(self.profile_versions) != {
            value.recipe_id for value in occurrences.values()
        }:
            raise ValueError(
                "profile_versions recipe IDs must exactly match occurrence recipe IDs"
            )

        self.notes = self.notes.strip() if self.notes else None
        return self
