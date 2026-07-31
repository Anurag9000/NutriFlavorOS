"""Add immutable conversion and storage-policy evidence history.

Revision ID: 20260801_0007
Revises: 20260801_0006
Create Date: 2026-08-01
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260801_0007"
down_revision: Union[str, None] = "20260801_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        current = value
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).isoformat()
    return str(value)


def _hash(payload: dict) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _create_conversion_versions() -> None:
    if "ingredient_conversion_versions" in _tables():
        return
    op.create_table(
        "ingredient_conversion_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("from_unit", sa.String(), nullable=False),
        sa.Column("to_unit", sa.String(), nullable=False),
        sa.Column("record_version", sa.String(), nullable=False),
        sa.Column("multiplier_min", sa.Float(), nullable=False),
        sa.Column("multiplier_max", sa.Float(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("source_version", sa.String(), nullable=False),
        sa.Column("evidence_status", sa.String(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("supersedes_conversion_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_status IN ('draft','external_unverified','reviewed','legacy_unreviewed')",
            name="ck_conversion_version_status",
        ),
        sa.CheckConstraint(
            "multiplier_min > 0",
            name="ck_conversion_version_min_positive",
        ),
        sa.CheckConstraint(
            "multiplier_max >= multiplier_min",
            name="ck_conversion_version_range",
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_conversion_version_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_conversion_id"],
            ["ingredient_conversion_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_name",
            "from_unit",
            "to_unit",
            "record_version",
            name="uq_conversion_version_natural_key",
        ),
    )
    op.create_index(
        "ix_ingredient_conversion_versions_canonical_name",
        "ingredient_conversion_versions",
        ["canonical_name"],
    )
    op.create_index(
        "ix_ingredient_conversion_versions_evidence_status",
        "ingredient_conversion_versions",
        ["evidence_status"],
    )
    op.create_index(
        "ix_ingredient_conversion_versions_content_hash",
        "ingredient_conversion_versions",
        ["content_hash"],
    )
    op.create_index(
        "ix_ingredient_conversion_versions_active",
        "ingredient_conversion_versions",
        ["active"],
    )


def _create_storage_versions() -> None:
    if "storage_policy_versions" in _tables():
        return
    op.create_table(
        "storage_policy_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_key", sa.String(), nullable=False),
        sa.Column("policy_version", sa.String(), nullable=False),
        sa.Column("food_category", sa.String(), nullable=False),
        sa.Column("storage_state", sa.String(), nullable=False),
        sa.Column("duration_min_hours", sa.Float(), nullable=True),
        sa.Column("duration_max_hours", sa.Float(), nullable=True),
        sa.Column("maximum_temperature_c", sa.Float(), nullable=True),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("source_version", sa.String(), nullable=False),
        sa.Column("evidence_status", sa.String(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("safety_scope", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("supersedes_policy_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_status IN ('draft','external_unverified','reviewed','legacy_unreviewed')",
            name="ck_storage_policy_version_status",
        ),
        sa.CheckConstraint(
            "duration_min_hours IS NULL OR duration_min_hours >= 0",
            name="ck_storage_policy_version_min_nonnegative",
        ),
        sa.CheckConstraint(
            "duration_max_hours IS NULL OR duration_max_hours >= 0",
            name="ck_storage_policy_version_max_nonnegative",
        ),
        sa.CheckConstraint(
            "duration_max_hours IS NULL OR duration_min_hours IS NULL OR duration_max_hours >= duration_min_hours",
            name="ck_storage_policy_version_duration_range",
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_storage_policy_version_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_policy_id"],
            ["storage_policy_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_key",
            "policy_version",
            name="uq_storage_policy_version_natural_key",
        ),
    )
    op.create_index(
        "ix_storage_policy_versions_policy_key",
        "storage_policy_versions",
        ["policy_key"],
    )
    op.create_index(
        "ix_storage_policy_versions_food_category",
        "storage_policy_versions",
        ["food_category"],
    )
    op.create_index(
        "ix_storage_policy_versions_storage_state",
        "storage_policy_versions",
        ["storage_state"],
    )
    op.create_index(
        "ix_storage_policy_versions_evidence_status",
        "storage_policy_versions",
        ["evidence_status"],
    )
    op.create_index(
        "ix_storage_policy_versions_content_hash",
        "storage_policy_versions",
        ["content_hash"],
    )
    op.create_index(
        "ix_storage_policy_versions_active",
        "storage_policy_versions",
        ["active"],
    )


def _create_leftover_links() -> None:
    if "leftover_storage_policy_evidence" in _tables():
        return
    op.create_table(
        "leftover_storage_policy_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("leftover_id", sa.Integer(), nullable=False),
        sa.Column("storage_policy_version_id", sa.Integer(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["leftover_id"],
            ["leftover_batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["storage_policy_version_id"],
            ["storage_policy_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "leftover_id",
            name="uq_leftover_storage_policy_evidence_leftover",
        ),
    )
    op.create_index(
        "ix_leftover_storage_policy_evidence_leftover_id",
        "leftover_storage_policy_evidence",
        ["leftover_id"],
    )
    op.create_index(
        "ix_leftover_storage_policy_evidence_storage_policy_version_id",
        "leftover_storage_policy_evidence",
        ["storage_policy_version_id"],
    )


def _copy_legacy_conversions() -> None:
    tables = _tables()
    if "ingredient_conversions" not in tables:
        return
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, canonical_name, from_unit, to_unit, multiplier_min, "
            "multiplier_max, source_name, source_url, source_version, "
            "evidence_status, reviewed_at, notes, active "
            "FROM ingredient_conversions ORDER BY id"
        )
    ).mappings().all()
    reviewed_counts = Counter(
        (
            str(row["canonical_name"]).strip().lower(),
            str(row["from_unit"]).strip().lower(),
            str(row["to_unit"]).strip().lower(),
        )
        for row in rows
        if bool(row["active"])
        and str(row["evidence_status"]) == "reviewed"
        and row["reviewed_at"] is not None
    )
    now = datetime.now(timezone.utc)
    for row in rows:
        canonical_name = " ".join(
            str(row["canonical_name"]).strip().lower().split()
        )
        from_unit = str(row["from_unit"]).strip().lower()
        to_unit = str(row["to_unit"]).strip().lower()
        original_status = str(row["evidence_status"] or "legacy_unreviewed")
        status = (
            original_status
            if original_status
            in {"draft", "external_unverified", "reviewed", "legacy_unreviewed"}
            else "legacy_unreviewed"
        )
        reviewed = status == "reviewed" and row["reviewed_at"] is not None
        uniquely_active_reviewed = (
            reviewed
            and bool(row["active"])
            and reviewed_counts[(canonical_name, from_unit, to_unit)] == 1
        )
        active = (
            uniquely_active_reviewed
            if reviewed
            else bool(row["active"])
        )
        record_version = f"legacy-{row['id']}"
        payload = {
            "canonical_name": canonical_name,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "record_version": record_version,
            "multiplier_min": float(row["multiplier_min"]),
            "multiplier_max": float(row["multiplier_max"]),
            "source_name": str(row["source_name"]),
            "source_url": str(row["source_url"]),
            "source_version": str(row["source_version"]),
            "evidence_status": status,
            "reviewed_at": _iso(row["reviewed_at"]),
            "reviewed_by": (
                "Legacy migration; original reviewer was not recorded"
                if reviewed
                else None
            ),
            "notes": row["notes"],
        }
        bind.execute(
            sa.text(
                "INSERT INTO ingredient_conversion_versions "
                "(canonical_name, from_unit, to_unit, record_version, "
                "multiplier_min, multiplier_max, source_name, source_url, "
                "source_version, evidence_status, reviewed_at, reviewed_by, "
                "notes, content_hash, supersedes_conversion_id, active, "
                "created_at, updated_at) VALUES "
                "(:canonical_name, :from_unit, :to_unit, :record_version, "
                ":multiplier_min, :multiplier_max, :source_name, :source_url, "
                ":source_version, :evidence_status, :reviewed_at, :reviewed_by, "
                ":notes, :content_hash, NULL, :active, :created_at, :updated_at)"
            ),
            {
                **payload,
                "content_hash": _hash(payload),
                "active": active,
                "created_at": now,
                "updated_at": now,
            },
        )


def _copy_legacy_storage_policies() -> dict[str, int]:
    tables = _tables()
    if "storage_policies" not in tables:
        return {}
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, policy_key, food_category, storage_state, "
            "duration_min_hours, duration_max_hours, maximum_temperature_c, "
            "source_name, source_url, reviewed_at, safety_scope, notes, active "
            "FROM storage_policies ORDER BY id"
        )
    ).mappings().all()
    now = datetime.now(timezone.utc)
    active_ids: dict[str, int] = {}
    for row in rows:
        policy_key = str(row["policy_key"]).strip().lower()
        reviewed = row["reviewed_at"] is not None
        status = "reviewed" if reviewed else "legacy_unreviewed"
        active = bool(row["active"]) and reviewed
        policy_version = f"legacy-{row['id']}"
        payload = {
            "policy_key": policy_key,
            "policy_version": policy_version,
            "food_category": str(row["food_category"]),
            "storage_state": str(row["storage_state"]).strip().lower(),
            "duration_min_hours": row["duration_min_hours"],
            "duration_max_hours": row["duration_max_hours"],
            "maximum_temperature_c": row["maximum_temperature_c"],
            "source_name": str(row["source_name"]),
            "source_url": str(row["source_url"]),
            "source_version": "legacy-source-record",
            "evidence_status": status,
            "reviewed_at": _iso(row["reviewed_at"]),
            "reviewed_by": (
                "Legacy migration; original reviewer was not recorded"
                if reviewed
                else None
            ),
            "safety_scope": str(row["safety_scope"]),
            "notes": row["notes"],
        }
        result = bind.execute(
            sa.text(
                "INSERT INTO storage_policy_versions "
                "(policy_key, policy_version, food_category, storage_state, "
                "duration_min_hours, duration_max_hours, maximum_temperature_c, "
                "source_name, source_url, source_version, evidence_status, "
                "reviewed_at, reviewed_by, safety_scope, notes, content_hash, "
                "supersedes_policy_id, active, created_at, updated_at) VALUES "
                "(:policy_key, :policy_version, :food_category, :storage_state, "
                ":duration_min_hours, :duration_max_hours, :maximum_temperature_c, "
                ":source_name, :source_url, :source_version, :evidence_status, "
                ":reviewed_at, :reviewed_by, :safety_scope, :notes, :content_hash, "
                "NULL, :active, :created_at, :updated_at) RETURNING id"
            ),
            {
                **payload,
                "content_hash": _hash(payload),
                "active": active,
                "created_at": now,
                "updated_at": now,
            },
        )
        identifier = result.scalar_one()
        if active:
            active_ids[policy_key] = int(identifier)
    return active_ids


def _copy_leftover_policy_links(active_policy_ids: dict[str, int]) -> None:
    if not active_policy_ids or "leftover_batches" not in _tables():
        return
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, storage_policy_key FROM leftover_batches "
            "WHERE storage_policy_key IS NOT NULL ORDER BY id"
        )
    ).mappings().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        policy_id = active_policy_ids.get(
            str(row["storage_policy_key"]).strip().lower()
        )
        if policy_id is None:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO leftover_storage_policy_evidence "
                "(leftover_id, storage_policy_version_id, linked_at) "
                "VALUES (:leftover_id, :policy_id, :linked_at)"
            ),
            {
                "leftover_id": row["id"],
                "policy_id": policy_id,
                "linked_at": now,
            },
        )


def _create_partial_unique_indexes() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect in {"sqlite", "postgresql"}:
        op.create_index(
            "uq_active_reviewed_conversion_key",
            "ingredient_conversion_versions",
            ["canonical_name", "from_unit", "to_unit"],
            unique=True,
            sqlite_where=sa.text(
                "active = 1 AND evidence_status = 'reviewed'"
            ),
            postgresql_where=sa.text(
                "active IS TRUE AND evidence_status = 'reviewed'"
            ),
        )
        op.create_index(
            "uq_active_reviewed_storage_policy_key",
            "storage_policy_versions",
            ["policy_key"],
            unique=True,
            sqlite_where=sa.text(
                "active = 1 AND evidence_status = 'reviewed'"
            ),
            postgresql_where=sa.text(
                "active IS TRUE AND evidence_status = 'reviewed'"
            ),
        )


def upgrade() -> None:
    _create_conversion_versions()
    _create_storage_versions()
    _create_leftover_links()
    _copy_legacy_conversions()
    active_policy_ids = _copy_legacy_storage_policies()
    _copy_leftover_policy_links(active_policy_ids)
    _create_partial_unique_indexes()


def downgrade() -> None:
    tables = _tables()
    if "leftover_storage_policy_evidence" in tables:
        op.drop_table("leftover_storage_policy_evidence")
    if "storage_policy_versions" in tables:
        op.drop_table("storage_policy_versions")
    if "ingredient_conversion_versions" in tables:
        op.drop_table("ingredient_conversion_versions")
