"""Atomic local dataset/model registry with integrity and promotion gates.

This registry is filesystem-backed and offline-only. Request handlers must
never auto-promote or automatically load artifacts from it.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.research.cards import DatasetCard, ModelCard
from backend.research.catalog import RiskLevel, get_catalog
from backend.research.manifest import fingerprint_file


class RegistryStage(str, Enum):
    REGISTERED = "registered"
    CANDIDATE = "candidate"
    CHAMPION = "champion"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class RegistryEntry(BaseModel):
    kind: str = Field(pattern=r"^(dataset|model)$")
    item_id: str
    version: str
    stage: RegistryStage = RegistryStage.REGISTERED
    card: Dict[str, Any]
    artifact_path: Optional[str] = None
    artifact_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    evaluations: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.item_id}:{self.version}"


class PromotionDecision(BaseModel):
    allowed: bool
    target_stage: RegistryStage
    missing_gates: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class LocalArtifactRegistry:
    def __init__(
        self,
        root: Path,
        *,
        lock_timeout_seconds: float = 15.0,
        stale_lock_seconds: float = 120.0,
    ):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "registry.json"
        self.lock_path = self.root / ".registry.lock"
        self.lock_timeout_seconds = max(0.1, float(lock_timeout_seconds))
        self.stale_lock_seconds = max(
            self.lock_timeout_seconds, float(stale_lock_seconds)
        )
        self._lock = threading.RLock()
        with self._lock, self._process_lock():
            if not self.index_path.exists():
                self._atomic_write({"schema_version": 1, "entries": {}})

    @contextmanager
    def _process_lock(self) -> Iterator[None]:
        """Acquire a portable exclusive lock using atomic file creation.

        This avoids platform-specific `fcntl`/`msvcrt` behavior. A crashed
        process can leave a lock file, so stale files are removed only after a
        conservative age threshold. The registry remains offline-only; this is
        not a distributed network lock.
        """

        deadline = time.monotonic() + self.lock_timeout_seconds
        descriptor: Optional[int] = None
        while descriptor is None:
            try:
                descriptor = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                payload = (
                    f"pid={os.getpid()} thread={threading.get_ident()} "
                    f"created={datetime.now(timezone.utc).isoformat()}\n"
                ).encode("utf-8")
                os.write(descriptor, payload)
                os.fsync(descriptor)
            except FileExistsError:
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                    if age > self.stale_lock_seconds:
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out acquiring artifact-registry lock: {self.lock_path}"
                    )
                time.sleep(0.05)
        try:
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass

    def _load(self) -> Dict[str, Any]:
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Artifact registry is unreadable") from exc
        if payload.get("schema_version") != 1 or not isinstance(
            payload.get("entries"), dict
        ):
            raise RuntimeError("Unsupported artifact-registry schema")
        return payload

    def _atomic_write(self, payload: Dict[str, Any]) -> None:
        temporary = self.root / (
            f".registry.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}.tmp"
        )
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                json.dump(
                    payload,
                    handle,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.index_path)
            # Persist the directory entry where the platform permits it.
            try:
                directory_fd = os.open(self.root, os.O_RDONLY)
            except (OSError, TypeError):
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                finally:
                    os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _save_entry(
        self, entry: RegistryEntry, *, overwrite: bool = False
    ) -> RegistryEntry:
        with self._lock, self._process_lock():
            payload = self._load()
            if entry.key in payload["entries"] and not overwrite:
                raise ValueError(f"Registry entry already exists: {entry.key}")
            payload["entries"][entry.key] = entry.model_dump(mode="json")
            self._atomic_write(payload)
        return entry

    def register_dataset(
        self, card: DatasetCard, artifact_path: Optional[Path] = None
    ) -> RegistryEntry:
        if card.dataset_id not in {item.id for item in get_catalog().datasets}:
            raise ValueError(
                "Dataset card identifier is not present in the research catalog"
            )
        digest = None
        resolved_path = None
        if artifact_path is not None:
            resolved = artifact_path.resolve(strict=True)
            if not resolved.is_file():
                raise ValueError("Dataset artifact must be a regular file")
            digest = fingerprint_file(resolved)
            if card.checksum_sha256 and card.checksum_sha256 != digest:
                raise ValueError("Dataset checksum does not match the artifact")
            resolved_path = str(resolved)
        now = self._now()
        return self._save_entry(
            RegistryEntry(
                kind="dataset",
                item_id=card.dataset_id,
                version=card.version,
                card=card.model_dump(mode="json"),
                artifact_path=resolved_path,
                artifact_sha256=digest or card.checksum_sha256,
                created_at=now,
                updated_at=now,
            )
        )

    def register_model(self, card: ModelCard, artifact_path: Path) -> RegistryEntry:
        if card.model_id not in {item.id for item in get_catalog().models}:
            raise ValueError(
                "Model card identifier is not present in the research catalog"
            )
        resolved = artifact_path.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("Model artifact must be a regular file")
        digest = fingerprint_file(resolved)
        if card.artifact_sha256 and card.artifact_sha256 != digest:
            raise ValueError("Model-card checksum does not match the artifact")
        card_payload = card.model_copy(update={"artifact_sha256": digest})
        now = self._now()
        return self._save_entry(
            RegistryEntry(
                kind="model",
                item_id=card.model_id,
                version=card.version,
                card=card_payload.model_dump(mode="json"),
                artifact_path=str(resolved),
                artifact_sha256=digest,
                created_at=now,
                updated_at=now,
            )
        )

    def get(self, kind: str, item_id: str, version: str) -> RegistryEntry:
        key = f"{kind}:{item_id}:{version}"
        payload = self._load()["entries"].get(key)
        if payload is None:
            raise KeyError(key)
        return RegistryEntry.model_validate(payload)

    def list(
        self,
        *,
        kind: Optional[str] = None,
        stage: Optional[RegistryStage] = None,
    ) -> List[RegistryEntry]:
        entries = [
            RegistryEntry.model_validate(value)
            for value in self._load()["entries"].values()
        ]
        if kind is not None:
            entries = [entry for entry in entries if entry.kind == kind]
        if stage is not None:
            entries = [entry for entry in entries if entry.stage == stage]
        return sorted(
            entries, key=lambda item: (item.kind, item.item_id, item.version)
        )

    def verify_integrity(self, entry: RegistryEntry) -> bool:
        if not entry.artifact_path or not entry.artifact_sha256:
            return False
        path = Path(entry.artifact_path)
        return path.is_file() and fingerprint_file(path) == entry.artifact_sha256

    def promotion_decision(
        self,
        entry: RegistryEntry,
        *,
        target_stage: RegistryStage,
        gate_results: Dict[str, bool],
    ) -> PromotionDecision:
        if entry.kind != "model":
            return PromotionDecision(
                allowed=False,
                target_stage=target_stage,
                reasons=["Only model entries have candidate/champion stages"],
            )
        card = ModelCard.model_validate(entry.card)
        missing = sorted(
            gate
            for gate in card.promotion_gates
            if not gate_results.get(gate, False)
        )
        reasons: List[str] = []
        if not self.verify_integrity(entry):
            missing.append("artifact_integrity")
            reasons.append(
                "The registered artifact is missing or its checksum changed"
            )
        if (
            target_stage == RegistryStage.CHAMPION
            and entry.stage
            not in {RegistryStage.CANDIDATE, RegistryStage.CHAMPION}
        ):
            reasons.append(
                "A model must enter candidate stage before champion promotion"
            )
        if (
            card.risk == RiskLevel.CLINICAL
            and target_stage == RegistryStage.CHAMPION
            and (not card.clinical_validation or not card.human_approval_id)
        ):
            reasons.append(
                "Clinical-risk models require documented clinical validation "
                "and human approval"
            )
        return PromotionDecision(
            allowed=not missing and not reasons,
            target_stage=target_stage,
            missing_gates=sorted(set(missing)),
            reasons=reasons,
        )

    def promote(
        self,
        item_id: str,
        version: str,
        *,
        target_stage: RegistryStage,
        gate_results: Dict[str, bool],
        evaluation: Optional[Dict[str, Any]] = None,
    ) -> RegistryEntry:
        with self._lock, self._process_lock():
            payload = self._load()
            key = f"model:{item_id}:{version}"
            raw = payload["entries"].get(key)
            if raw is None:
                raise KeyError(key)
            entry = RegistryEntry.model_validate(raw)
            decision = self.promotion_decision(
                entry,
                target_stage=target_stage,
                gate_results=gate_results,
            )
            if not decision.allowed:
                detail = "; ".join(
                    decision.reasons
                    + [f"missing gates: {', '.join(decision.missing_gates)}"]
                )
                raise ValueError(f"Promotion blocked: {detail}")
            now = self._now()
            if target_stage == RegistryStage.CHAMPION:
                for other_key, value in payload["entries"].items():
                    other = RegistryEntry.model_validate(value)
                    if (
                        other.kind == "model"
                        and other.item_id == item_id
                        and other.stage == RegistryStage.CHAMPION
                        and other.key != entry.key
                    ):
                        payload["entries"][other_key]["stage"] = (
                            RegistryStage.ARCHIVED.value
                        )
                        payload["entries"][other_key]["updated_at"] = now
            entry.stage = target_stage
            entry.evaluations = {
                **entry.evaluations,
                **(evaluation or {}),
                "gate_results": gate_results,
            }
            entry.updated_at = now
            payload["entries"][entry.key] = entry.model_dump(mode="json")
            self._atomic_write(payload)
            return entry
