"""Idempotent immutable registration for reviewed built-in storage guidance."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.evidence_history import (
    EvidenceRecordStatus,
    StoragePolicyVersionInput,
)
from backend.evidence_history_models import DBStoragePolicyVersion
from backend.services.conversion_service import OFFICIAL_STORAGE_POLICIES
from backend.services.evidence_history_service import (
    storage_policy_content_hash,
    utcnow,
)


OFFICIAL_POLICY_VERSION = "official-2026-07-31"
OFFICIAL_SOURCE_VERSION = "reviewed-2026-07-31"
OFFICIAL_REVIEWER = "NutriFlavorOS evidence review 2026-07-31"


def official_storage_policy_payloads() -> tuple[StoragePolicyVersionInput, ...]:
    values = []
    for raw in OFFICIAL_STORAGE_POLICIES:
        values.append(
            StoragePolicyVersionInput(
                policy_key=str(raw["policy_key"]),
                policy_version=OFFICIAL_POLICY_VERSION,
                food_category=str(raw["food_category"]),
                storage_state=str(raw["storage_state"]),
                duration_min_hours=raw.get("duration_min_hours"),
                duration_max_hours=raw.get("duration_max_hours"),
                maximum_temperature_c=raw.get("maximum_temperature_c"),
                source_name=str(raw["source_name"]),
                source_url=str(raw["source_url"]),
                source_version=OFFICIAL_SOURCE_VERSION,
                evidence_status=EvidenceRecordStatus.REVIEWED,
                reviewed_at=raw["reviewed_at"],
                reviewed_by=OFFICIAL_REVIEWER,
                safety_scope=str(raw["safety_scope"]),
                notes=raw.get("notes"),
                active=True,
            )
        )
    return tuple(sorted(values, key=lambda value: value.policy_key))


def _seed_once(db: Session) -> int:
    created = 0
    now = utcnow()
    for payload in official_storage_policy_payloads():
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
            if existing.content_hash != content_hash:
                raise RuntimeError(
                    "Built-in storage policy content changed without a policy-version bump: "
                    f"{payload.policy_key}"
                )
            continue

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
        if current is not None:
            current.active = False
            current.updated_at = now
            db.add(current)
            db.flush()

        db.add(
            DBStoragePolicyVersion(
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
                active=True,
                created_at=now,
                updated_at=now,
            )
        )
        db.flush()
        created += 1
    db.commit()
    return created


def seed_official_storage_policy_versions(db: Session) -> int:
    """Register the complete built-in policy set as one transaction.

    A concurrent replica may win the same insert race. In that case, the loser
    accepts the state only when every expected natural version and content hash
    is present; otherwise startup fails rather than masking partial evidence.
    """

    try:
        return _seed_once(db)
    except IntegrityError as exc:
        db.rollback()
        expected = {
            (value.policy_key, value.policy_version): storage_policy_content_hash(value)
            for value in official_storage_policy_payloads()
        }
        rows = (
            db.query(DBStoragePolicyVersion)
            .filter(
                DBStoragePolicyVersion.policy_version == OFFICIAL_POLICY_VERSION
            )
            .all()
        )
        observed = {
            (value.policy_key, value.policy_version): value.content_hash
            for value in rows
        }
        if observed == expected:
            return 0
        raise RuntimeError(
            "Concurrent immutable storage-policy seeding left an incomplete or contradictory state"
        ) from exc
