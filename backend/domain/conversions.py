"""Evidence-backed ingredient conversions and storage policy contracts."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class IngredientConversionCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=240)
    from_unit: str = Field(min_length=1, max_length=32)
    to_unit: str = Field(min_length=1, max_length=32)
    multiplier_min: float = Field(gt=0)
    multiplier_max: float = Field(gt=0)
    source_name: str = Field(min_length=1, max_length=160)
    source_url: str = Field(min_length=1, max_length=1000)
    source_version: str = Field(min_length=1, max_length=160)
    evidence_status: str = Field(
        default="external_unverified",
        pattern=r"^(external_unverified|reviewed_external|reviewed_manual)$",
    )
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_range(self):
        if self.multiplier_max < self.multiplier_min:
            raise ValueError("multiplier_max cannot be less than multiplier_min")
        if self.from_unit == self.to_unit and (
            abs(self.multiplier_min - 1.0) > 1e-9
            or abs(self.multiplier_max - 1.0) > 1e-9
        ):
            raise ValueError("same-unit conversion must use multiplier 1")
        return self


class IngredientConversionView(IngredientConversionCreate):
    id: int
    active: bool

    model_config = {"from_attributes": True}


class ConversionRequest(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=240)
    quantity_min: float = Field(ge=0)
    quantity_max: float = Field(ge=0)
    from_unit: str = Field(min_length=1, max_length=32)
    to_unit: str = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_range(self):
        if self.quantity_max < self.quantity_min:
            raise ValueError("quantity_max cannot be less than quantity_min")
        return self


class ConversionResult(BaseModel):
    canonical_name: str
    input_quantity_min: float
    input_quantity_max: float
    input_unit: str
    output_quantity_min: float
    output_quantity_max: float
    output_unit: str
    evidence: IngredientConversionView
    warnings: List[str] = Field(default_factory=list)


class StoragePolicyView(BaseModel):
    id: int
    policy_key: str
    food_category: str
    storage_state: str
    duration_min_hours: Optional[float]
    duration_max_hours: Optional[float]
    maximum_temperature_c: Optional[float]
    source_name: str
    source_url: str
    reviewed_at: datetime
    safety_scope: str
    notes: Optional[str]
    active: bool

    model_config = {"from_attributes": True}
