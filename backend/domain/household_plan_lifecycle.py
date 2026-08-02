"""Strict contracts for persisted household meal-plan review and approval."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models import PlanResponse


class StrictHouseholdPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class HouseholdPlanStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    CANCELLED = "cancelled"


class HouseholdPlanEventType(str, Enum):
    APPROVED = "approved"
    CANCELLED = "cancelled"


class HouseholdPlanTransitionRequest(StrictHouseholdPlanModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(
        min_length=8,
        max_length=200,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("reason cannot be blank")
        return normalized


class PersistedHouseholdPlanView(StrictHouseholdPlanModel):
    id: int
    household_id: str
    user_id: str
    schema_version: str
    plan: PlanResponse
    status: HouseholdPlanStatus
    version: int
    approved_by_user_id: Optional[str]
    approved_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class HouseholdPlanEventView(StrictHouseholdPlanModel):
    id: int
    plan_id: int
    household_id: str
    event_type: HouseholdPlanEventType
    actor_user_id: str
    from_status: HouseholdPlanStatus
    to_status: HouseholdPlanStatus
    reason: str
    metadata: Dict[str, Any]
    idempotency_key: str
    request_fingerprint: str
    created_at: datetime
