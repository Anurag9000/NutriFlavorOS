"""SQLAlchemy models for immutable conversion and storage-policy evidence."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)

from backend.database import Base, utcnow


class DBIngredientConversionVersion(Base):
    __tablename__ = "ingredient_conversion_versions"
    __table_args__ = (
        UniqueConstraint(
            "canonical_name",
            "from_unit",
            "to_unit",
            "record_version",
            name="uq_conversion_version_natural_key",
        ),
        CheckConstraint(
            "evidence_status IN ('draft','external_unverified','reviewed','legacy_unreviewed')",
            name="ck_conversion_version_status",
        ),
        CheckConstraint(
            "multiplier_min > 0",
            name="ck_conversion_version_min_positive",
        ),
        CheckConstraint(
            "multiplier_max >= multiplier_min",
            name="ck_conversion_version_range",
        ),
        CheckConstraint(
            "length(content_hash) = 64",
            name="ck_conversion_version_hash_length",
        ),
        Index(
            "uq_active_reviewed_conversion_key",
            "canonical_name",
            "from_unit",
            "to_unit",
            unique=True,
            sqlite_where=text(
                "active = 1 AND evidence_status = 'reviewed'"
            ),
            postgresql_where=text(
                "active IS TRUE AND evidence_status = 'reviewed'"
            ),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(String, nullable=False, index=True)
    from_unit = Column(String, nullable=False)
    to_unit = Column(String, nullable=False)
    record_version = Column(String, nullable=False)
    multiplier_min = Column(Float, nullable=False)
    multiplier_max = Column(Float, nullable=False)
    source_name = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    source_version = Column(String, nullable=False)
    evidence_status = Column(String, nullable=False, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    supersedes_conversion_id = Column(
        Integer,
        ForeignKey(
            "ingredient_conversion_versions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBStoragePolicyVersion(Base):
    __tablename__ = "storage_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "policy_key",
            "policy_version",
            name="uq_storage_policy_version_natural_key",
        ),
        CheckConstraint(
            "evidence_status IN ('draft','external_unverified','reviewed','legacy_unreviewed')",
            name="ck_storage_policy_version_status",
        ),
        CheckConstraint(
            "duration_min_hours IS NULL OR duration_min_hours >= 0",
            name="ck_storage_policy_version_min_nonnegative",
        ),
        CheckConstraint(
            "duration_max_hours IS NULL OR duration_max_hours >= 0",
            name="ck_storage_policy_version_max_nonnegative",
        ),
        CheckConstraint(
            "duration_max_hours IS NULL OR duration_min_hours IS NULL OR duration_max_hours >= duration_min_hours",
            name="ck_storage_policy_version_duration_range",
        ),
        CheckConstraint(
            "length(content_hash) = 64",
            name="ck_storage_policy_version_hash_length",
        ),
        Index(
            "uq_active_reviewed_storage_policy_key",
            "policy_key",
            unique=True,
            sqlite_where=text(
                "active = 1 AND evidence_status = 'reviewed'"
            ),
            postgresql_where=text(
                "active IS TRUE AND evidence_status = 'reviewed'"
            ),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_key = Column(String, nullable=False, index=True)
    policy_version = Column(String, nullable=False)
    food_category = Column(String, nullable=False, index=True)
    storage_state = Column(String, nullable=False, index=True)
    duration_min_hours = Column(Float, nullable=True)
    duration_max_hours = Column(Float, nullable=True)
    maximum_temperature_c = Column(Float, nullable=True)
    source_name = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    source_version = Column(String, nullable=False)
    evidence_status = Column(String, nullable=False, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, nullable=True)
    safety_scope = Column(String, nullable=False)
    notes = Column(String, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    supersedes_policy_id = Column(
        Integer,
        ForeignKey("storage_policy_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBLeftoverStoragePolicyEvidence(Base):
    __tablename__ = "leftover_storage_policy_evidence"
    __table_args__ = (
        UniqueConstraint(
            "leftover_id",
            name="uq_leftover_storage_policy_evidence_leftover",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    leftover_id = Column(
        Integer,
        ForeignKey("leftover_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_policy_version_id = Column(
        Integer,
        ForeignKey("storage_policy_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    linked_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
