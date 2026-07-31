"""Versioned dataset and model cards for research artifacts.

Cards are executable contracts, not marketing documents. They record intended
and prohibited uses, provenance, evaluation requirements, and promotion gates.
Generating a card never enables a model in request-time product behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from backend.research.catalog import DatasetSpec, ModelSpec, RiskLevel, get_catalog


class DatasetCard(BaseModel):
    dataset_id: str
    version: str = Field(min_length=1, max_length=120)
    name: str
    source_urls: List[str] = Field(default_factory=list)
    license: str
    modalities: List[str] = Field(default_factory=list)
    task_ids: List[str] = Field(default_factory=list)
    intended_uses: List[str] = Field(default_factory=list)
    prohibited_uses: List[str] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)
    collection_period: Optional[str] = None
    geography: List[str] = Field(default_factory=list)
    contains_personal_data: bool = False
    consent_basis: Optional[str] = None
    deidentification: Optional[str] = None
    split_strategy: Optional[str] = None
    leakage_controls: List[str] = Field(default_factory=list)
    quality_checks: List[str] = Field(default_factory=list)
    known_limitations: List[str] = Field(default_factory=list)
    checksum_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def validate_privacy_contract(self):
        if self.contains_personal_data and not self.consent_basis:
            raise ValueError("Personal-data datasets require an explicit consent_basis")
        return self


class ModelCard(BaseModel):
    model_id: str
    version: str = Field(min_length=1, max_length=120)
    name: str
    family: str
    task_ids: List[str] = Field(default_factory=list)
    dataset_ids: List[str] = Field(default_factory=list)
    risk: RiskLevel
    artifact_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    framework: Optional[str] = None
    intended_uses: List[str] = Field(default_factory=list)
    prohibited_uses: List[str] = Field(default_factory=list)
    evaluation_metrics: Dict[str, Any] = Field(default_factory=dict)
    calibration_metrics: Dict[str, Any] = Field(default_factory=dict)
    subgroup_metrics: Dict[str, Any] = Field(default_factory=dict)
    ood_metrics: Dict[str, Any] = Field(default_factory=dict)
    promotion_gates: List[str] = Field(default_factory=list)
    known_limitations: List[str] = Field(default_factory=list)
    training_data_statement: str = "not_recorded"
    reproducibility_statement: str = "not_recorded"
    clinical_validation: bool = False
    human_approval_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def validate_high_risk_claims(self):
        if self.risk == RiskLevel.CLINICAL and self.clinical_validation and not self.human_approval_id:
            raise ValueError("Clinical validation claims require a human_approval_id")
        return self


def _default_model_gates(spec: ModelSpec) -> List[str]:
    gates = ["artifact_integrity", "data_provenance", "license_review", "reproducibility"]
    if spec.risk in {RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CLINICAL}:
        gates.extend(["offline_benchmark", "ood_evaluation"])
    if spec.risk in {RiskLevel.HIGH, RiskLevel.CLINICAL}:
        gates.extend(["calibration", "subgroup_evaluation", "human_review"])
    if spec.risk == RiskLevel.CLINICAL:
        gates.extend(["external_validation", "uncertainty_coverage", "contraindication_safety", "clinical_review"])
    return gates


def build_dataset_card(dataset_id: str, *, version: str = "unversioned") -> DatasetCard:
    catalog = get_catalog()
    spec: DatasetSpec = next(item for item in catalog.datasets if item.id == dataset_id)
    prohibited = ["Use outside the documented license and source terms"]
    if spec.contains_personal_data:
        prohibited.extend(["Training without an approved consent and retention basis", "Re-identification or cross-context identity linkage"])
    return DatasetCard(
        dataset_id=spec.id,
        version=version,
        name=spec.name,
        source_urls=[spec.source_url],
        license=spec.license,
        modalities=list(spec.modalities),
        task_ids=list(spec.tasks),
        intended_uses=["Offline research for the catalogued tasks"],
        prohibited_uses=prohibited,
        provenance=[spec.notes] if spec.notes else [],
        contains_personal_data=spec.contains_personal_data,
        consent_basis="required_before_use" if spec.contains_personal_data else None,
        leakage_controls=["Entity/group-aware splitting when repeated entities are present"],
        quality_checks=["Schema validation", "Duplicate detection", "Source and license verification"],
        known_limitations=[spec.notes] if spec.notes else [],
    )


def build_model_card(model_id: str, *, version: str = "unversioned") -> ModelCard:
    catalog = get_catalog()
    spec: ModelSpec = next(item for item in catalog.models if item.id == model_id)
    prohibited = ["Automatic enablement in request-time product behavior"]
    if spec.risk in {RiskLevel.HIGH, RiskLevel.CLINICAL}:
        prohibited.append("Use as autonomous medical, allergy, medication, or food-safety advice")
    return ModelCard(
        model_id=spec.id,
        version=version,
        name=spec.name,
        family=spec.family,
        task_ids=list(spec.tasks),
        risk=spec.risk,
        intended_uses=["Offline evaluation under the registered experiment contracts"],
        prohibited_uses=prohibited,
        promotion_gates=_default_model_gates(spec),
        known_limitations=[spec.notes] if spec.notes else [],
    )
