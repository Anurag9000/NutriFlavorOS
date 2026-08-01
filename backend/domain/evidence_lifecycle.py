"""Offline lifecycle contracts for immutable food-evidence versions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class EvidenceTargetKind(str, Enum):
    CONVERSION = "conversion"
    STORAGE_POLICY = "storage_policy"


class EvidenceLifecycleAction(str, Enum):
    DEACTIVATED = "deactivated"
    REJECTED = "rejected"


class EvidenceLifecycleRequest(BaseModel):
    target_kind: EvidenceTargetKind
    target_id: int = Field(ge=1)
    action: EvidenceLifecycleAction
    actor: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(
        min_length=8,
        max_length=240,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self):
        self.actor = " ".join(self.actor.strip().split())
        self.reason = " ".join(self.reason.strip().split())
        if not self.actor:
            raise ValueError("actor cannot be blank")
        if not self.reason:
            raise ValueError("reason cannot be blank")
        return self


class EvidenceLifecycleBatchDocument(BaseModel):
    document_version: str = Field(
        default="evidence-lifecycle-v1",
        pattern=r"^evidence-lifecycle-v[0-9]+$",
    )
    actions: List[EvidenceLifecycleRequest] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def validate_batch(self):
        keys = [value.idempotency_key for value in self.actions]
        if len(keys) != len(set(keys)):
            raise ValueError("Lifecycle batch contains duplicate idempotency keys")
        targets = [(value.target_kind.value, value.target_id) for value in self.actions]
        if len(targets) != len(set(targets)):
            raise ValueError("Lifecycle batch contains multiple actions for one evidence target")
        return self


class EvidenceLifecycleEventView(BaseModel):
    id: int
    target_kind: EvidenceTargetKind
    target_id: int
    action: EvidenceLifecycleAction
    actor: str
    reason: str
    metadata: Dict[str, Any]
    idempotency_key: str
    request_fingerprint: str
    target_record_version: str
    target_content_hash: str
    target_was_active: bool
    created_at: str


class EvidenceLifecycleBatchResult(BaseModel):
    events: List[EvidenceLifecycleEventView]
    changed_target_count: int
    already_inactive_count: int
    idempotent_count: int
