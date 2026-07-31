"""Immutable conversion and storage-policy evidence contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class EvidenceRecordStatus(str, Enum):
    DRAFT = "draft"
    EXTERNAL_UNVERIFIED = "external_unverified"
    REVIEWED = "reviewed"
    LEGACY_UNREVIEWED = "legacy_unreviewed"


class IngredientConversionVersionInput(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=300)
    from_unit: str = Field(min_length=1, max_length=80)
    to_unit: str = Field(min_length=1, max_length=80)
    record_version: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    multiplier_min: float = Field(gt=0)
    multiplier_max: float = Field(gt=0)
    source_name: str = Field(min_length=1, max_length=300)
    source_url: str = Field(min_length=1, max_length=2000)
    source_version: str = Field(min_length=1, max_length=200)
    evidence_status: EvidenceRecordStatus = EvidenceRecordStatus.DRAFT
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=4000)
    active: bool = True

    @model_validator(mode="after")
    def validate_record(self):
        self.canonical_name = " ".join(self.canonical_name.strip().lower().split())
        self.from_unit = self.from_unit.strip().lower()
        self.to_unit = self.to_unit.strip().lower()
        if self.from_unit == self.to_unit:
            raise ValueError("from_unit and to_unit must differ")
        if self.multiplier_max < self.multiplier_min:
            raise ValueError("multiplier_max cannot be less than multiplier_min")
        if self.evidence_status == EvidenceRecordStatus.REVIEWED:
            if self.reviewed_at is None:
                raise ValueError("reviewed conversion evidence requires reviewed_at")
            if not self.reviewed_by or not self.reviewed_by.strip():
                raise ValueError("reviewed conversion evidence requires reviewed_by")
        return self


class IngredientConversionVersionView(IngredientConversionVersionInput):
    id: int
    content_hash: str
    supersedes_conversion_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoragePolicyVersionInput(BaseModel):
    policy_key: str = Field(
        min_length=1,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    policy_version: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    food_category: str = Field(min_length=1, max_length=300)
    storage_state: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    duration_min_hours: Optional[float] = Field(default=None, ge=0)
    duration_max_hours: Optional[float] = Field(default=None, ge=0)
    maximum_temperature_c: Optional[float] = Field(default=None, ge=-100, le=100)
    source_name: str = Field(min_length=1, max_length=300)
    source_url: str = Field(min_length=1, max_length=2000)
    source_version: str = Field(min_length=1, max_length=200)
    evidence_status: EvidenceRecordStatus = EvidenceRecordStatus.DRAFT
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = Field(default=None, max_length=300)
    safety_scope: str = Field(min_length=1, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=4000)
    active: bool = True

    @model_validator(mode="after")
    def validate_record(self):
        self.policy_key = self.policy_key.strip().lower()
        self.food_category = " ".join(self.food_category.strip().split())
        self.storage_state = self.storage_state.strip().lower()
        if (
            self.duration_min_hours is not None
            and self.duration_max_hours is not None
            and self.duration_max_hours < self.duration_min_hours
        ):
            raise ValueError(
                "duration_max_hours cannot be less than duration_min_hours"
            )
        if self.evidence_status == EvidenceRecordStatus.REVIEWED:
            if self.reviewed_at is None:
                raise ValueError("reviewed storage evidence requires reviewed_at")
            if not self.reviewed_by or not self.reviewed_by.strip():
                raise ValueError("reviewed storage evidence requires reviewed_by")
        return self


class StoragePolicyVersionView(StoragePolicyVersionInput):
    id: int
    content_hash: str
    supersedes_policy_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversionApplicationRequest(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=300)
    quantity_min: float = Field(ge=0)
    quantity_max: float = Field(ge=0)
    from_unit: str = Field(min_length=1, max_length=80)
    to_unit: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_range(self):
        if self.quantity_max < self.quantity_min:
            raise ValueError("quantity_max cannot be less than quantity_min")
        return self


class ConversionApplicationResult(BaseModel):
    canonical_name: str
    from_unit: str
    to_unit: str
    input_quantity_min: float
    input_quantity_max: float
    output_quantity_min: float
    output_quantity_max: float
    conversion_record_id: int
    conversion_record_version: str
    conversion_content_hash: str
    source_name: str
    source_url: str
    source_version: str
    evidence_status: EvidenceRecordStatus
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
