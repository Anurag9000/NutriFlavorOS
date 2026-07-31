"""Reproducible experiment configuration, fingerprints, and artifact manifests."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field, model_validator


class ExperimentRunConfig(BaseModel):
    experiment_id: str = Field(min_length=1, max_length=160)
    baseline: str = Field(min_length=1, max_length=160)
    dataset_path: Optional[str] = None
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    allow_user_data: bool = False
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def prevent_accidental_user_data(self):
        path = (self.dataset_path or "").lower()
        sensitive_tokens = ("nutriflavor.db", "feedback", "inventory", "user_db", "meal_plans")
        if any(token in path for token in sensitive_tokens) and not self.allow_user_data:
            raise ValueError("Potential user-owned data requires allow_user_data=true")
        return self


class ArtifactEntry(BaseModel):
    path: str
    sha256: str
    bytes: int = Field(ge=0)
    media_type: str = "application/octet-stream"


class RunManifest(BaseModel):
    run_id: str
    experiment_id: str
    baseline: str
    seed: int
    status: str
    created_at: str
    dataset_fingerprint: Optional[str] = None
    model_fingerprint: Optional[str] = None
    environment: Dict[str, Any]
    config: Dict[str, Any]
    metrics: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[ArtifactEntry] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fingerprint_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256_bytes(payload)


def artifact_entry(path: Path, *, root: Optional[Path] = None, media_type: str = "application/octet-stream") -> ArtifactEntry:
    resolved = path.resolve()
    display = str(resolved.relative_to(root.resolve())) if root and root.resolve() in resolved.parents else str(resolved)
    return ArtifactEntry(path=display, sha256=fingerprint_file(resolved), bytes=resolved.stat().st_size, media_type=media_type)


def environment_snapshot() -> Dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "git_sha": os.getenv("GIT_SHA"),
        "timezone": "UTC",
    }


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def create_manifest(config: ExperimentRunConfig) -> RunManifest:
    return RunManifest(
        run_id=str(uuid4()),
        experiment_id=config.experiment_id,
        baseline=config.baseline,
        seed=config.seed,
        status="created",
        created_at=datetime.now(timezone.utc).isoformat(),
        environment=environment_snapshot(),
        config=config.model_dump(mode="json"),
    )
