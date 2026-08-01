"""Preflight and atomic batch registration for immutable food evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, List, Literal, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.evidence_history import (
    EvidenceRecordStatus,
    IngredientConversionVersionInput,
    IngredientConversionVersionView,
    StoragePolicyVersionInput,
    StoragePolicyVersionView,
)
from backend.evidence_history_models import (
    DBIngredientConversionVersion,
    DBStoragePolicyVersion,
)
from backend.services.evidence_history_service import (
    _conversion_view,
    _lock_evidence_key,
    _policy_view,
    conversion_content_hash,
    storage_policy_content_hash,
    utcnow,
)


EvidenceKind = Literal["conversion", "storage_policy"]
PlannedAction = Literal[
    "idempotent_existing",
    "register_inactive_or_unreviewed",
    "register_active_reviewed",
    "register_and_supersede",
]


@dataclass(frozen=True)
class EvidenceImportPreview:
    evidence_kind: EvidenceKind
    natural_key: str
    record_version: str
    content_hash: str
    evidence_status: str
    requested_active: bool
    planned_action: PlannedAction
    existing_record_id: int | None
    supersedes_record_id: int | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FoodEvidenceBatchResult:
    conversions: tuple[IngredientConversionVersionView, ...]
    storage_policies: tuple[StoragePolicyVersionView, ...]
    previews: tuple[EvidenceImportPreview, ...]
    inserted_count: int
    idempotent_count: int


def conversion_natural_key(payload: IngredientConversionVersionInput) -> str:
    return f"{payload.canonical_name}|{payload.from_unit}|{payload.to_unit}"


def conversion_version_key(payload: IngredientConversionVersionInput) -> str:
    return f"{conversion_natural_key(payload)}|{payload.record_version}"


def storage_policy_version_key(payload: StoragePolicyVersionInput) -> str:
    return f"{payload.policy_key}|{payload.policy_version}"


def _validate_batch_shape(
    conversions: Sequence[IngredientConversionVersionInput],
    policies: Sequence[StoragePolicyVersionInput],
) -> None:
    conversion_versions = [conversion_version_key(value) for value in conversions]
    if len(conversion_versions) != len(set(conversion_versions)):
        raise ValueError("Food-evidence import contains duplicate conversion version keys")
    policy_versions = [storage_policy_version_key(value) for value in policies]
    if len(policy_versions) != len(set(policy_versions)):
        raise ValueError("Food-evidence import contains duplicate storage-policy version keys")

    conversion_active_reviewed: dict[str, int] = {}
    for value in conversions:
        if value.active and value.evidence_status == EvidenceRecordStatus.REVIEWED:
            key = conversion_natural_key(value)
            conversion_active_reviewed[key] = conversion_active_reviewed.get(key, 0) + 1
    ambiguous_conversions = sorted(
        key for key, count in conversion_active_reviewed.items() if count > 1
    )
    if ambiguous_conversions:
        raise ValueError(
            "A batch may contain at most one active reviewed conversion successor per natural key: "
            + ", ".join(ambiguous_conversions)
        )

    policy_active_reviewed: dict[str, int] = {}
    for value in policies:
        if value.active and value.evidence_status == EvidenceRecordStatus.REVIEWED:
            policy_active_reviewed[value.policy_key] = (
                policy_active_reviewed.get(value.policy_key, 0) + 1
            )
    ambiguous_policies = sorted(
        key for key, count in policy_active_reviewed.items() if count > 1
    )
    if ambiguous_policies:
        raise ValueError(
            "A batch may contain at most one active reviewed storage-policy successor per policy key: "
            + ", ".join(ambiguous_policies)
        )


def _latest_reviewed_conversion_snapshot(
    db: Session,
    payload: IngredientConversionVersionInput,
) -> DBIngredientConversionVersion | None:
    """Return the current predecessor without taking a database row lock.

    Dry-run preflight is an advisory snapshot, not a reservation. Apply mode
    first obtains transaction advisory locks for every natural key, then calls
    the same snapshot logic inside that protected transaction.
    """

    return (
        db.query(DBIngredientConversionVersion)
        .filter(
            DBIngredientConversionVersion.canonical_name == payload.canonical_name,
            DBIngredientConversionVersion.from_unit == payload.from_unit,
            DBIngredientConversionVersion.to_unit == payload.to_unit,
            DBIngredientConversionVersion.evidence_status
            == EvidenceRecordStatus.REVIEWED.value,
        )
        .order_by(
            DBIngredientConversionVersion.active.desc(),
            DBIngredientConversionVersion.created_at.desc(),
            DBIngredientConversionVersion.id.desc(),
        )
        .first()
    )


def _latest_reviewed_policy_snapshot(
    db: Session,
    payload: StoragePolicyVersionInput,
) -> DBStoragePolicyVersion | None:
    """Return the current policy predecessor without taking a row lock."""

    return (
        db.query(DBStoragePolicyVersion)
        .filter(
            DBStoragePolicyVersion.policy_key == payload.policy_key,
            DBStoragePolicyVersion.evidence_status
            == EvidenceRecordStatus.REVIEWED.value,
        )
        .order_by(
            DBStoragePolicyVersion.active.desc(),
            DBStoragePolicyVersion.created_at.desc(),
            DBStoragePolicyVersion.id.desc(),
        )
        .first()
    )


def _conversion_preview(
    db: Session,
    payload: IngredientConversionVersionInput,
) -> EvidenceImportPreview:
    content_hash = conversion_content_hash(payload)
    existing = (
        db.query(DBIngredientConversionVersion)
        .filter(
            DBIngredientConversionVersion.canonical_name == payload.canonical_name,
            DBIngredientConversionVersion.from_unit == payload.from_unit,
            DBIngredientConversionVersion.to_unit == payload.to_unit,
            DBIngredientConversionVersion.record_version == payload.record_version,
        )
        .first()
    )
    if existing is not None:
        if existing.content_hash != content_hash:
            raise ValueError(
                "Conversion record version already exists with different evidence content: "
                + conversion_version_key(payload)
            )
        return EvidenceImportPreview(
            evidence_kind="conversion",
            natural_key=conversion_natural_key(payload),
            record_version=payload.record_version,
            content_hash=content_hash,
            evidence_status=payload.evidence_status.value,
            requested_active=payload.active,
            planned_action="idempotent_existing",
            existing_record_id=existing.id,
            supersedes_record_id=existing.supersedes_conversion_id,
        )

    predecessor = None
    if payload.active and payload.evidence_status == EvidenceRecordStatus.REVIEWED:
        predecessor = _latest_reviewed_conversion_snapshot(db, payload)
    if predecessor is not None:
        action: PlannedAction = "register_and_supersede"
    elif payload.active and payload.evidence_status == EvidenceRecordStatus.REVIEWED:
        action = "register_active_reviewed"
    else:
        action = "register_inactive_or_unreviewed"
    return EvidenceImportPreview(
        evidence_kind="conversion",
        natural_key=conversion_natural_key(payload),
        record_version=payload.record_version,
        content_hash=content_hash,
        evidence_status=payload.evidence_status.value,
        requested_active=payload.active,
        planned_action=action,
        existing_record_id=None,
        supersedes_record_id=(predecessor.id if predecessor is not None else None),
    )


def _policy_preview(
    db: Session,
    payload: StoragePolicyVersionInput,
) -> EvidenceImportPreview:
    content_hash = storage_policy_content_hash(payload)
    existing = (
        db.query(DBStoragePolicyVersion)
        .filter(
            DBStoragePolicyVersion.policy_key == payload.policy_key,
            DBStoragePolicyVersion.policy_version == payload.policy_version,
        )
        .first()
    )
    if existing is not None:
        if existing.content_hash != content_hash:
            raise ValueError(
                "Storage policy version already exists with different evidence content: "
                + storage_policy_version_key(payload)
            )
        return EvidenceImportPreview(
            evidence_kind="storage_policy",
            natural_key=payload.policy_key,
            record_version=payload.policy_version,
            content_hash=content_hash,
            evidence_status=payload.evidence_status.value,
            requested_active=payload.active,
            planned_action="idempotent_existing",
            existing_record_id=existing.id,
            supersedes_record_id=existing.supersedes_policy_id,
        )

    predecessor = None
    if payload.active and payload.evidence_status == EvidenceRecordStatus.REVIEWED:
        predecessor = _latest_reviewed_policy_snapshot(db, payload)
    if predecessor is not None:
        action: PlannedAction = "register_and_supersede"
    elif payload.active and payload.evidence_status == EvidenceRecordStatus.REVIEWED:
        action = "register_active_reviewed"
    else:
        action = "register_inactive_or_unreviewed"
    return EvidenceImportPreview(
        evidence_kind="storage_policy",
        natural_key=payload.policy_key,
        record_version=payload.policy_version,
        content_hash=content_hash,
        evidence_status=payload.evidence_status.value,
        requested_active=payload.active,
        planned_action=action,
        existing_record_id=None,
        supersedes_record_id=(predecessor.id if predecessor is not None else None),
    )


def preflight_food_evidence(
    db: Session,
    conversions: Iterable[IngredientConversionVersionInput],
    policies: Iterable[StoragePolicyVersionInput],
) -> List[EvidenceImportPreview]:
    conversion_values = sorted(
        list(conversions),
        key=lambda value: (conversion_natural_key(value), value.record_version),
    )
    policy_values = sorted(
        list(policies),
        key=lambda value: (value.policy_key, value.policy_version),
    )
    _validate_batch_shape(conversion_values, policy_values)
    return [
        *[_conversion_preview(db, value) for value in conversion_values],
        *[_policy_preview(db, value) for value in policy_values],
    ]


def _acquire_batch_locks(
    db: Session,
    conversions: Sequence[IngredientConversionVersionInput],
    policies: Sequence[StoragePolicyVersionInput],
) -> None:
    lock_keys = {
        *(f"conversion:{conversion_natural_key(value)}" for value in conversions),
        *(f"storage-policy:{value.policy_key}" for value in policies),
    }
    for lock_key in sorted(lock_keys):
        namespace, key = lock_key.split(":", 1)
        _lock_evidence_key(db, namespace, key)


def register_food_evidence_atomic(
    db: Session,
    conversions: Iterable[IngredientConversionVersionInput],
    policies: Iterable[StoragePolicyVersionInput],
) -> FoodEvidenceBatchResult:
    conversion_values = sorted(
        list(conversions),
        key=lambda value: (conversion_natural_key(value), value.record_version),
    )
    policy_values = sorted(
        list(policies),
        key=lambda value: (value.policy_key, value.policy_version),
    )
    _validate_batch_shape(conversion_values, policy_values)
    _acquire_batch_locks(db, conversion_values, policy_values)
    previews = preflight_food_evidence(db, conversion_values, policy_values)
    preview_by_key = {
        (value.evidence_kind, value.natural_key, value.record_version): value
        for value in previews
    }
    now = utcnow()
    conversion_rows: list[DBIngredientConversionVersion] = []
    policy_rows: list[DBStoragePolicyVersion] = []

    try:
        for payload in conversion_values:
            preview = preview_by_key[
                ("conversion", conversion_natural_key(payload), payload.record_version)
            ]
            if preview.planned_action == "idempotent_existing":
                row = db.get(DBIngredientConversionVersion, preview.existing_record_id)
                if row is None:
                    raise RuntimeError("Idempotent conversion record disappeared during import")
                conversion_rows.append(row)
                continue
            predecessor = None
            if preview.supersedes_record_id is not None:
                predecessor = db.get(
                    DBIngredientConversionVersion,
                    preview.supersedes_record_id,
                )
                if predecessor is None:
                    raise RuntimeError("Conversion supersession target disappeared during import")
                if predecessor.active:
                    predecessor.active = False
                    predecessor.updated_at = now
                    db.add(predecessor)
                    db.flush()
            row = DBIngredientConversionVersion(
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
                content_hash=preview.content_hash,
                supersedes_conversion_id=preview.supersedes_record_id,
                active=payload.active,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            conversion_rows.append(row)

        for payload in policy_values:
            preview = preview_by_key[
                ("storage_policy", payload.policy_key, payload.policy_version)
            ]
            if preview.planned_action == "idempotent_existing":
                row = db.get(DBStoragePolicyVersion, preview.existing_record_id)
                if row is None:
                    raise RuntimeError("Idempotent storage-policy record disappeared during import")
                policy_rows.append(row)
                continue
            predecessor = None
            if preview.supersedes_record_id is not None:
                predecessor = db.get(
                    DBStoragePolicyVersion,
                    preview.supersedes_record_id,
                )
                if predecessor is None:
                    raise RuntimeError("Storage-policy supersession target disappeared during import")
                if predecessor.active:
                    predecessor.active = False
                    predecessor.updated_at = now
                    db.add(predecessor)
                    db.flush()
            row = DBStoragePolicyVersion(
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
                content_hash=preview.content_hash,
                supersedes_policy_id=preview.supersedes_record_id,
                active=payload.active,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            policy_rows.append(row)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(
            "Immutable food-evidence batch conflicted with concurrent state; no batch rows were committed"
        ) from exc
    except Exception:
        db.rollback()
        raise

    for row in [*conversion_rows, *policy_rows]:
        db.refresh(row)
    inserted = sum(value.planned_action != "idempotent_existing" for value in previews)
    return FoodEvidenceBatchResult(
        conversions=tuple(_conversion_view(value) for value in conversion_rows),
        storage_policies=tuple(_policy_view(value) for value in policy_rows),
        previews=tuple(previews),
        inserted_count=inserted,
        idempotent_count=len(previews) - inserted,
    )
