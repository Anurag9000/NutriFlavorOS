"""Immutable conversion and storage-policy evidence services."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Iterable, List

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.evidence_history import (
    ConversionApplicationRequest,
    ConversionApplicationResult,
    EvidenceRecordStatus,
    IngredientConversionVersionInput,
    IngredientConversionVersionView,
    StoragePolicyVersionInput,
    StoragePolicyVersionView,
)
from backend.evidence_history_models import (
    DBIngredientConversionVersion,
    DBLeftoverStoragePolicyEvidence,
    DBStoragePolicyVersion,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash(payload: dict) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def conversion_content_hash(payload: IngredientConversionVersionInput) -> str:
    return _hash(
        {
            "canonical_name": payload.canonical_name,
            "from_unit": payload.from_unit,
            "to_unit": payload.to_unit,
            "record_version": payload.record_version,
            "multiplier_min": payload.multiplier_min,
            "multiplier_max": payload.multiplier_max,
            "source_name": payload.source_name,
            "source_url": payload.source_url,
            "source_version": payload.source_version,
            "evidence_status": payload.evidence_status.value,
            "reviewed_at": (
                payload.reviewed_at.isoformat() if payload.reviewed_at else None
            ),
            "reviewed_by": payload.reviewed_by,
            "notes": payload.notes,
        }
    )


def storage_policy_content_hash(payload: StoragePolicyVersionInput) -> str:
    return _hash(
        {
            "policy_key": payload.policy_key,
            "policy_version": payload.policy_version,
            "food_category": payload.food_category,
            "storage_state": payload.storage_state,
            "duration_min_hours": payload.duration_min_hours,
            "duration_max_hours": payload.duration_max_hours,
            "maximum_temperature_c": payload.maximum_temperature_c,
            "source_name": payload.source_name,
            "source_url": payload.source_url,
            "source_version": payload.source_version,
            "evidence_status": payload.evidence_status.value,
            "reviewed_at": (
                payload.reviewed_at.isoformat() if payload.reviewed_at else None
            ),
            "reviewed_by": payload.reviewed_by,
            "safety_scope": payload.safety_scope,
            "notes": payload.notes,
        }
    )


def _conversion_view(
    value: DBIngredientConversionVersion,
) -> IngredientConversionVersionView:
    return IngredientConversionVersionView(
        id=value.id,
        canonical_name=value.canonical_name,
        from_unit=value.from_unit,
        to_unit=value.to_unit,
        record_version=value.record_version,
        multiplier_min=value.multiplier_min,
        multiplier_max=value.multiplier_max,
        source_name=value.source_name,
        source_url=value.source_url,
        source_version=value.source_version,
        evidence_status=EvidenceRecordStatus(value.evidence_status),
        reviewed_at=value.reviewed_at,
        reviewed_by=value.reviewed_by,
        notes=value.notes,
        content_hash=value.content_hash,
        supersedes_conversion_id=value.supersedes_conversion_id,
        active=value.active,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _policy_view(value: DBStoragePolicyVersion) -> StoragePolicyVersionView:
    return StoragePolicyVersionView(
        id=value.id,
        policy_key=value.policy_key,
        policy_version=value.policy_version,
        food_category=value.food_category,
        storage_state=value.storage_state,
        duration_min_hours=value.duration_min_hours,
        duration_max_hours=value.duration_max_hours,
        maximum_temperature_c=value.maximum_temperature_c,
        source_name=value.source_name,
        source_url=value.source_url,
        source_version=value.source_version,
        evidence_status=EvidenceRecordStatus(value.evidence_status),
        reviewed_at=value.reviewed_at,
        reviewed_by=value.reviewed_by,
        safety_scope=value.safety_scope,
        notes=value.notes,
        content_hash=value.content_hash,
        supersedes_policy_id=value.supersedes_policy_id,
        active=value.active,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def register_conversion_version(
    db: Session,
    payload: IngredientConversionVersionInput,
) -> IngredientConversionVersionView:
    content_hash = conversion_content_hash(payload)
    existing = (
        db.query(DBIngredientConversionVersion)
        .filter(
            DBIngredientConversionVersion.canonical_name
            == payload.canonical_name,
            DBIngredientConversionVersion.from_unit == payload.from_unit,
            DBIngredientConversionVersion.to_unit == payload.to_unit,
            DBIngredientConversionVersion.record_version
            == payload.record_version,
        )
        .with_for_update()
        .first()
    )
    if existing is not None:
        if existing.content_hash == content_hash:
            return _conversion_view(existing)
        raise ValueError(
            "Conversion record version already exists with different evidence content"
        )

    current = None
    if payload.active and payload.evidence_status == EvidenceRecordStatus.REVIEWED:
        current = (
            db.query(DBIngredientConversionVersion)
            .filter(
                DBIngredientConversionVersion.canonical_name
                == payload.canonical_name,
                DBIngredientConversionVersion.from_unit == payload.from_unit,
                DBIngredientConversionVersion.to_unit == payload.to_unit,
                DBIngredientConversionVersion.evidence_status
                == EvidenceRecordStatus.REVIEWED.value,
                DBIngredientConversionVersion.active.is_(True),
            )
            .with_for_update()
            .first()
        )

    now = utcnow()
    if current is not None:
        current.active = False
        current.updated_at = now
        db.add(current)
        db.flush()

    value = DBIngredientConversionVersion(
        canonical_name=payload.canonical_name,
        from_unit=payload.from_unit,
        to_unit=payload.to_unit,
        record_version=payload.record_version,
        multiplier_min=payload.multiplier_min,
        multiplier_max=payload.multiplier_max,
        source_name=payload.source_name,
        source_url=payload.source_url,
        source_version=payload.source_version,
        evidence_status=payload.evidence_status.value,
        reviewed_at=payload.reviewed_at,
        reviewed_by=payload.reviewed_by,
        notes=payload.notes,
        content_hash=content_hash,
        supersedes_conversion_id=current.id if current is not None else None,
        active=payload.active,
        created_at=now,
        updated_at=now,
    )
    db.add(value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = (
            db.query(DBIngredientConversionVersion)
            .filter(
                DBIngredientConversionVersion.canonical_name
                == payload.canonical_name,
                DBIngredientConversionVersion.from_unit == payload.from_unit,
                DBIngredientConversionVersion.to_unit == payload.to_unit,
                DBIngredientConversionVersion.record_version
                == payload.record_version,
            )
            .first()
        )
        if winner is not None and winner.content_hash == content_hash:
            return _conversion_view(winner)
        raise ValueError(
            "Conversion version registration conflicted with concurrent evidence state"
        ) from exc
    db.refresh(value)
    return _conversion_view(value)


def register_storage_policy_version(
    db: Session,
    payload: StoragePolicyVersionInput,
) -> StoragePolicyVersionView:
    content_hash = storage_policy_content_hash(payload)
    existing = (
        db.query(DBStoragePolicyVersion)
        .filter(
            DBStoragePolicyVersion.policy_key == payload.policy_key,
            DBStoragePolicyVersion.policy_version == payload.policy_version,
        )
        .with_for_update()
        .first()
    )
    if existing is not None:
        if existing.content_hash == content_hash:
            return _policy_view(existing)
        raise ValueError(
            "Storage policy version already exists with different evidence content"
        )

    current = None
    if payload.active and payload.evidence_status == EvidenceRecordStatus.REVIEWED:
        current = (
            db.query(DBStoragePolicyVersion)
            .filter(
                DBStoragePolicyVersion.policy_key == payload.policy_key,
                DBStoragePolicyVersion.evidence_status
                == EvidenceRecordStatus.REVIEWED.value,
                DBStoragePolicyVersion.active.is_(True),
            )
            .with_for_update()
            .first()
        )

    now = utcnow()
    if current is not None:
        current.active = False
        current.updated_at = now
        db.add(current)
        db.flush()

    value = DBStoragePolicyVersion(
        policy_key=payload.policy_key,
        policy_version=payload.policy_version,
        food_category=payload.food_category,
        storage_state=payload.storage_state,
        duration_min_hours=payload.duration_min_hours,
        duration_max_hours=payload.duration_max_hours,
        maximum_temperature_c=payload.maximum_temperature_c,
        source_name=payload.source_name,
        source_url=payload.source_url,
        source_version=payload.source_version,
        evidence_status=payload.evidence_status.value,
        reviewed_at=payload.reviewed_at,
        reviewed_by=payload.reviewed_by,
        safety_scope=payload.safety_scope,
        notes=payload.notes,
        content_hash=content_hash,
        supersedes_policy_id=current.id if current is not None else None,
        active=payload.active,
        created_at=now,
        updated_at=now,
    )
    db.add(value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = (
            db.query(DBStoragePolicyVersion)
            .filter(
                DBStoragePolicyVersion.policy_key == payload.policy_key,
                DBStoragePolicyVersion.policy_version
                == payload.policy_version,
            )
            .first()
        )
        if winner is not None and winner.content_hash == content_hash:
            return _policy_view(winner)
        raise ValueError(
            "Storage policy version registration conflicted with concurrent evidence state"
        ) from exc
    db.refresh(value)
    return _policy_view(value)


def list_conversion_versions(
    db: Session,
    *,
    active_only: bool = True,
    reviewed_only: bool = False,
) -> List[IngredientConversionVersionView]:
    query = db.query(DBIngredientConversionVersion)
    if active_only:
        query = query.filter(DBIngredientConversionVersion.active.is_(True))
    if reviewed_only:
        query = query.filter(
            DBIngredientConversionVersion.evidence_status
            == EvidenceRecordStatus.REVIEWED.value
        )
    rows = query.order_by(
        DBIngredientConversionVersion.canonical_name,
        DBIngredientConversionVersion.from_unit,
        DBIngredientConversionVersion.to_unit,
        DBIngredientConversionVersion.created_at.desc(),
        DBIngredientConversionVersion.id.desc(),
    ).all()
    return [_conversion_view(value) for value in rows]


def list_storage_policy_versions(
    db: Session,
    *,
    active_only: bool = True,
    reviewed_only: bool = False,
) -> List[StoragePolicyVersionView]:
    query = db.query(DBStoragePolicyVersion)
    if active_only:
        query = query.filter(DBStoragePolicyVersion.active.is_(True))
    if reviewed_only:
        query = query.filter(
            DBStoragePolicyVersion.evidence_status
            == EvidenceRecordStatus.REVIEWED.value
        )
    rows = query.order_by(
        DBStoragePolicyVersion.policy_key,
        DBStoragePolicyVersion.created_at.desc(),
        DBStoragePolicyVersion.id.desc(),
    ).all()
    return [_policy_view(value) for value in rows]


def active_reviewed_storage_policy(
    db: Session,
    policy_key: str,
) -> StoragePolicyVersionView:
    value = (
        db.query(DBStoragePolicyVersion)
        .filter(
            DBStoragePolicyVersion.policy_key == policy_key.strip().lower(),
            DBStoragePolicyVersion.evidence_status
            == EvidenceRecordStatus.REVIEWED.value,
            DBStoragePolicyVersion.active.is_(True),
        )
        .first()
    )
    if value is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "reviewed_storage_policy_unavailable",
                "message": "No active reviewed storage policy version exists for this key",
            },
        )
    return _policy_view(value)


def apply_reviewed_conversion(
    db: Session,
    request: ConversionApplicationRequest,
) -> ConversionApplicationResult:
    canonical_name = " ".join(
        request.canonical_name.strip().lower().split()
    )
    from_unit = request.from_unit.strip().lower()
    to_unit = request.to_unit.strip().lower()
    value = (
        db.query(DBIngredientConversionVersion)
        .filter(
            DBIngredientConversionVersion.canonical_name == canonical_name,
            DBIngredientConversionVersion.from_unit == from_unit,
            DBIngredientConversionVersion.to_unit == to_unit,
            DBIngredientConversionVersion.evidence_status
            == EvidenceRecordStatus.REVIEWED.value,
            DBIngredientConversionVersion.active.is_(True),
        )
        .first()
    )
    if value is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "reviewed_conversion_unavailable",
                "message": (
                    "No exact active reviewed conversion exists for this ingredient and unit direction"
                ),
            },
        )
    return ConversionApplicationResult(
        canonical_name=canonical_name,
        from_unit=from_unit,
        to_unit=to_unit,
        input_quantity_min=request.quantity_min,
        input_quantity_max=request.quantity_max,
        output_quantity_min=request.quantity_min * value.multiplier_min,
        output_quantity_max=request.quantity_max * value.multiplier_max,
        conversion_record_id=value.id,
        conversion_record_version=value.record_version,
        conversion_content_hash=value.content_hash,
        source_name=value.source_name,
        source_url=value.source_url,
        source_version=value.source_version,
        evidence_status=EvidenceRecordStatus(value.evidence_status),
        reviewed_at=value.reviewed_at,
        reviewed_by=value.reviewed_by,
    )


def link_leftover_storage_policy_version(
    db: Session,
    *,
    leftover_id: int,
    storage_policy_version_id: int,
) -> DBLeftoverStoragePolicyEvidence:
    policy = db.get(DBStoragePolicyVersion, storage_policy_version_id)
    if policy is None:
        raise ValueError("Unknown storage_policy_version_id")
    if not policy.active or policy.evidence_status != EvidenceRecordStatus.REVIEWED.value:
        raise ValueError("Leftovers may link only to active reviewed storage policy versions")
    existing = (
        db.query(DBLeftoverStoragePolicyEvidence)
        .filter(DBLeftoverStoragePolicyEvidence.leftover_id == leftover_id)
        .first()
    )
    if existing is not None:
        if existing.storage_policy_version_id == storage_policy_version_id:
            return existing
        raise ValueError("Leftover already links to a different storage policy version")
    value = DBLeftoverStoragePolicyEvidence(
        leftover_id=leftover_id,
        storage_policy_version_id=storage_policy_version_id,
        linked_at=utcnow(),
    )
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


def storage_policy_for_leftover(
    db: Session,
    leftover_id: int,
) -> StoragePolicyVersionView | None:
    row = (
        db.query(DBStoragePolicyVersion)
        .join(
            DBLeftoverStoragePolicyEvidence,
            DBLeftoverStoragePolicyEvidence.storage_policy_version_id
            == DBStoragePolicyVersion.id,
        )
        .filter(DBLeftoverStoragePolicyEvidence.leftover_id == leftover_id)
        .first()
    )
    return _policy_view(row) if row is not None else None
