"""Contracts for reviewed household preparation calendars and schedules."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.domain.preparation import (
    PreparationAvailabilityWindow,
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_evidence import (
    DurationPolicy,
    RecipePreparationOccurrence,
)


class StrictPreparationOperationsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CalendarEvidenceStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"


class PreparationScheduleStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    INVALIDATED = "invalidated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PreparationScheduleEventType(str, Enum):
    CREATED = "created"
    APPROVED = "approved"
    INVALIDATED = "invalidated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _canonical_utc_timestamp(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_profile_versions(values: Dict[str, str]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = raw_key.strip()
        value = raw_value.strip()
        if not key or not value:
            raise ValueError("profile_versions keys and values cannot be blank")
        normalized[key] = value
    return dict(sorted(normalized.items()))


class PreparationOccurrenceSetDocument(StrictPreparationOperationsModel):
    document_version: Literal["preparation-occurrence-set-v1"] = (
        "preparation-occurrence-set-v1"
    )
    household_id: str = Field(min_length=1, max_length=200)
    occurrence_set_version: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    duration_policy: DurationPolicy = DurationPolicy.CONSERVATIVE_MAX
    occurrences: List[RecipePreparationOccurrence] = Field(
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def normalize_and_validate(self):
        self.household_id = self.household_id.strip()
        identifiers = [value.occurrence_id for value in self.occurrences]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("occurrence_id values must be unique")
        self.occurrences = sorted(
            self.occurrences,
            key=lambda value: value.occurrence_id,
        )
        return self


class HouseholdResourceInput(StrictPreparationOperationsModel):
    resource_id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    capacity: int = Field(default=1, ge=1, le=1000)
    resource_kind: str = Field(
        default="equipment",
        pattern=r"^[A-Za-z0-9_.:-]+$",
        min_length=1,
        max_length=80,
    )
    availability_windows: List[PreparationAvailabilityWindow] = Field(
        min_length=1,
        max_length=500,
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_and_validate(self):
        self.resource_id = self.resource_id.strip()
        self.label = " ".join(self.label.strip().split())
        self.resource_kind = self.resource_kind.strip().lower()
        if not self.resource_id or not self.label:
            raise ValueError("resource_id and label cannot be blank")
        ordered = sorted(
            self.availability_windows,
            key=lambda value: (value.start_minute, value.end_minute),
        )
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_minute < previous.end_minute:
                raise ValueError(
                    f"availability windows overlap for resource {self.resource_id}"
                )
        self.availability_windows = ordered
        return self


class ResourceCalendarVersionCreate(StrictPreparationOperationsModel):
    calendar_version: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    horizon_minutes: int = Field(default=24 * 60, ge=1, le=10080)
    timezone: str = Field(min_length=1, max_length=120)
    resources: List[HouseholdResourceInput] = Field(
        min_length=1,
        max_length=200,
    )
    evidence_status: CalendarEvidenceStatus = CalendarEvidenceStatus.DRAFT
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=4000)
    activate: bool = False
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )

    @model_validator(mode="after")
    def validate_calendar(self):
        self.timezone = self.timezone.strip()
        self.reviewed_at = _canonical_utc_timestamp(self.reviewed_at)
        self.reviewed_by = self.reviewed_by.strip() if self.reviewed_by else None
        self.notes = self.notes.strip() if self.notes else None
        identifiers = [value.resource_id for value in self.resources]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("resource_id values must be unique within a calendar")
        outside = sorted(
            value.resource_id
            for value in self.resources
            if any(
                window.end_minute > self.horizon_minutes
                for window in value.availability_windows
            )
        )
        if outside:
            raise ValueError(
                "resource windows exceed horizon_minutes for: "
                + ", ".join(outside)
            )
        if self.evidence_status == CalendarEvidenceStatus.REVIEWED:
            if not self.reviewed_at or not self.reviewed_by:
                raise ValueError(
                    "reviewed resource calendars require reviewed_at and reviewed_by"
                )
        elif self.activate:
            raise ValueError("only reviewed resource calendars can be activated")
        return self


class HouseholdResourceView(HouseholdResourceInput):
    id: int
    calendar_version_id: int


class ResourceCalendarVersionView(StrictPreparationOperationsModel):
    id: int
    household_id: str
    calendar_version: str
    horizon_minutes: int
    timezone: str
    evidence_status: CalendarEvidenceStatus
    reviewed_at: Optional[str]
    reviewed_by: Optional[str]
    notes: Optional[str]
    content_hash: str
    supersedes_calendar_id: Optional[int]
    active: bool
    created_by_user_id: str
    created_at: str
    updated_at: str
    resources: List[HouseholdResourceView]


class PersistedPreparationScheduleCreate(StrictPreparationOperationsModel):
    calendar_version_id: int = Field(ge=1)
    source_plan_id: Optional[int] = Field(default=None, ge=1)
    source_plan_version: Optional[int] = Field(default=None, ge=1)
    occurrence_set: PreparationOccurrenceSetDocument
    profile_versions: Dict[str, str] = Field(default_factory=dict, max_length=1000)
    schedule: PreparationScheduleResponse
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
        if self.schedule.unscheduled:
            raise ValueError("persisted schedules must be complete")
        self.profile_versions = _normalize_profile_versions(self.profile_versions)
        self.notes = self.notes.strip() if self.notes else None
        return self


class ScheduleStateTransitionRequest(StrictPreparationOperationsModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_reason(self):
        self.reason = " ".join(self.reason.strip().split())
        if not self.reason:
            raise ValueError("reason cannot be blank")
        return self


class PersistedPreparationScheduleView(StrictPreparationOperationsModel):
    id: int
    household_id: str
    calendar_version_id: int
    calendar_content_hash: str
    source_plan_id: Optional[int]
    source_plan_version: Optional[int]
    occurrence_set_version: str
    occurrence_set_hash: str
    occurrence_set: Optional[PreparationOccurrenceSetDocument] = None
    profile_versions: Dict[str, str]
    schedule_request: Optional[PreparationScheduleRequest] = None
    schedule_request_hash: Optional[str] = None
    replay_status: Literal[
        "replayable",
        "legacy_request_missing",
        "legacy_occurrence_set_missing",
    ] = "legacy_request_missing"
    schedule: PreparationScheduleResponse
    schedule_hash: str
    status: PreparationScheduleStatus
    version: int
    notes: Optional[str]
    created_by_user_id: str
    approved_by_user_id: Optional[str]
    approved_at: Optional[str]
    invalidated_at: Optional[str]
    invalidation_reason: Optional[str]
    created_at: str
    updated_at: str


class PreparationScheduleEventView(StrictPreparationOperationsModel):
    id: int
    schedule_id: int
    household_id: str
    event_type: PreparationScheduleEventType
    actor_user_id: str
    from_status: Optional[PreparationScheduleStatus]
    to_status: PreparationScheduleStatus
    reason: str
    metadata: Dict[str, Any]
    idempotency_key: str
    request_fingerprint: str
    created_at: str
