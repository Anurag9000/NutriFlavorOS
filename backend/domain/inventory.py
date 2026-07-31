"""Household, pantry, inventory-event, and leftover domain contracts.

The contracts preserve quantity ranges and unit families. They never convert
between mass, volume, count, or culinary units without an explicit conversion.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class InventoryEventType(str, Enum):
    PURCHASE = "purchase"
    CONSUME = "consume"
    ADJUST = "adjust"
    DISCARD = "discard"
    LEFTOVER_CREATE = "leftover_create"
    LEFTOVER_CONSUME = "leftover_consume"


class QuantityRange(BaseModel):
    quantity_min: float = Field(ge=0)
    quantity_max: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_range(self):
        if self.quantity_max < self.quantity_min:
            raise ValueError("quantity_max cannot be less than quantity_min")
        return self


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)


class HouseholdMemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    linked_user_id: Optional[str] = Field(default=None, max_length=320)
    servings_multiplier: float = Field(default=1.0, gt=0, le=20)
    allergies: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)
    disliked_ingredients: List[str] = Field(default_factory=list)
    active: bool = True


class PantryItemCreate(BaseModel):
    ingredient_name: str = Field(min_length=1, max_length=240)
    quantity: QuantityRange
    display_name: Optional[str] = Field(default=None, max_length=240)
    expires_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    source: str = Field(default="manual", min_length=1, max_length=64)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=160)


class InventoryMutation(BaseModel):
    quantity: QuantityRange
    reason: Optional[str] = Field(default=None, max_length=500)
    expected_version: Optional[int] = Field(default=None, ge=1)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=160)


class LeftoverCreate(BaseModel):
    recipe_id: str = Field(min_length=1, max_length=160)
    portions_available: float = Field(gt=0, le=1000)
    cooked_at: datetime
    expires_at: Optional[datetime] = None
    frozen: bool = False
    notes: Optional[str] = Field(default=None, max_length=1000)
    source_plan_id: Optional[int] = Field(default=None, ge=1)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=160)


class LeftoverConsume(BaseModel):
    portions: float = Field(gt=0, le=1000)
    expected_version: Optional[int] = Field(default=None, ge=1)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=160)


class HouseholdView(BaseModel):
    id: str
    owner_user_id: str
    name: str
    timezone: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HouseholdMemberView(BaseModel):
    id: int
    household_id: str
    display_name: str
    linked_user_id: Optional[str]
    servings_multiplier: float
    allergies: List[str]
    dietary_restrictions: List[str]
    disliked_ingredients: List[str]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PantryItemView(BaseModel):
    id: int
    household_id: str
    canonical_name: str
    display_name: str
    quantity_min: float
    quantity_max: float
    unit: str
    expires_at: Optional[datetime]
    opened_at: Optional[datetime]
    source: str
    metadata: Dict[str, Any] = Field(validation_alias="item_metadata")
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryEventView(BaseModel):
    id: int
    household_id: str
    pantry_item_id: Optional[int]
    leftover_id: Optional[int]
    event_type: InventoryEventType
    quantity_min: float
    quantity_max: float
    unit: str
    reason: Optional[str]
    metadata: Dict[str, Any] = Field(validation_alias="event_metadata")
    idempotency_key: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class LeftoverView(BaseModel):
    id: int
    household_id: str
    recipe_id: str
    source_plan_id: Optional[int]
    portions_available: float
    cooked_at: datetime
    expires_at: Optional[datetime]
    frozen: bool
    notes: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReconciledShoppingItem(BaseModel):
    canonical_name: str
    display_name: str
    unit: str
    required_min: float
    required_max: float
    pantry_min: float
    pantry_max: float
    buy_min: float
    buy_max: float
    coverage_status: str
    expiring_quantity_max: float = 0.0
    source_recipe_ids: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class BatchPrepTask(BaseModel):
    recipe_id: str
    recipe_name: str
    total_portions: float
    first_day: int
    scheduled_day: int
    occurrences: int
    meal_slots: List[str]
    storage_guidance_status: str = "requires_verified_recipe_specific_policy"
