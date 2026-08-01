"""Contracts for offline immutable food-evidence imports."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, model_validator

from backend.domain.evidence_history import (
    IngredientConversionVersionInput,
    StoragePolicyVersionInput,
)


class FoodEvidenceImportDocument(BaseModel):
    document_version: str = Field(
        default="food-evidence-import-v1",
        pattern=r"^food-evidence-import-v[0-9]+$",
    )
    conversion_versions: List[IngredientConversionVersionInput] = Field(
        default_factory=list,
        max_length=10000,
    )
    storage_policy_versions: List[StoragePolicyVersionInput] = Field(
        default_factory=list,
        max_length=10000,
    )

    @model_validator(mode="after")
    def require_records(self):
        if not self.conversion_versions and not self.storage_policy_versions:
            raise ValueError("Food-evidence import document contains no records")
        return self
