"""Household invitations, roles, reservations, and planning contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.models import PlanResponse


class HouseholdRole(str, Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"


ROLE_RANK = {
    HouseholdRole.VIEWER: 10,
    HouseholdRole.EDITOR: 20,
    HouseholdRole.OWNER: 30,
}


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("A valid email address is required")
        return normalized
    role: HouseholdRole = HouseholdRole.VIEWER
    expires_in_hours: int = Field(default=72, ge=1, le=24 * 30)

    @model_validator(mode="after")
    def owner_role_not_invitable(self):
        if self.role == HouseholdRole.OWNER:
            raise ValueError("Ownership transfer requires a separate reviewed workflow")
        return self


class InvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class InvitationView(BaseModel):
    id: str
    household_id: str
    invited_email: str
    role: HouseholdRole
    expires_at: datetime
    accepted_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_by_user_id: Optional[str]
    created_at: datetime
    acceptance_token: Optional[str] = None

    model_config = {"from_attributes": True}


class HouseholdMemberUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    role: Optional[HouseholdRole] = None
    servings_multiplier: Optional[float] = Field(default=None, gt=0, le=20)
    allergies: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None
    disliked_ingredients: Optional[List[str]] = None
    target_calories: Optional[int] = Field(default=None, gt=0, le=20000)
    target_protein_g: Optional[int] = Field(default=None, ge=0, le=2000)
    target_carbs_g: Optional[int] = Field(default=None, ge=0, le=4000)
    target_fat_g: Optional[int] = Field(default=None, ge=0, le=2000)
    active: Optional[bool] = None

    @model_validator(mode="after")
    def owner_role_not_assignable(self):
        if self.role == HouseholdRole.OWNER:
            raise ValueError("Ownership transfer requires a separate reviewed workflow")
        return self


class ReservationStatus(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class ReservationView(BaseModel):
    id: int
    household_id: str
    pantry_item_id: Optional[int]
    plan_id: int
    canonical_name: str
    quantity_min: float
    quantity_max: float
    unit: str
    status: ReservationStatus
    expires_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReservationMutation(BaseModel):
    expected_version: Optional[int] = Field(default=None, ge=1)
    reason: Optional[str] = Field(default=None, max_length=500)


class HouseholdPlanRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=31)
    reserve_inventory: bool = True
    reservation_hours: int = Field(default=48, ge=1, le=24 * 14)
    include_inactive_members: bool = False


class HouseholdTargetSummary(BaseModel):
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    member_count: int
    servings_multiplier: float
    source_status: str
    member_sources: Dict[str, str] = Field(default_factory=dict)


class HouseholdPlanResponse(BaseModel):
    household_id: str
    plan_id: int
    plan_schema_version: str
    household_plan_schema_version: str
    plan: PlanResponse
    target_summary: HouseholdTargetSummary
    pantry_coverage_score: float
    reservations: List[ReservationView] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
