"""Persistence models for household preparation calendars and schedules."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)

from backend.database import Base, utcnow


class DBResourceCalendarVersion(Base):
    __tablename__ = "resource_calendar_versions"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "calendar_version",
            name="uq_resource_calendar_household_version",
        ),
        UniqueConstraint(
            "household_id",
            "idempotency_key",
            name="uq_resource_calendar_household_idempotency",
        ),
        CheckConstraint(
            "evidence_status IN ('draft','reviewed')",
            name="ck_resource_calendar_evidence_status",
        ),
        CheckConstraint(
            "horizon_minutes >= 1 AND horizon_minutes <= 10080",
            name="ck_resource_calendar_horizon",
        ),
        CheckConstraint(
            "length(content_hash) = 64",
            name="ck_resource_calendar_hash_length",
        ),
        CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_resource_calendar_request_fingerprint_length",
        ),
        Index(
            "uq_active_reviewed_resource_calendar_household",
            "household_id",
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
    household_id = Column(
        String,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    calendar_version = Column(String, nullable=False)
    horizon_minutes = Column(Integer, nullable=False)
    timezone = Column(String, nullable=False)
    evidence_status = Column(String, nullable=False, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    supersedes_calendar_id = Column(
        Integer,
        ForeignKey("resource_calendar_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    active = Column(Boolean, nullable=False, default=False, index=True)
    created_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key = Column(String, nullable=False)
    request_fingerprint = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DBHouseholdPreparationResource(Base):
    __tablename__ = "household_preparation_resources"
    __table_args__ = (
        UniqueConstraint(
            "calendar_version_id",
            "resource_id",
            name="uq_household_preparation_resource_calendar_key",
        ),
        CheckConstraint(
            "capacity >= 1 AND capacity <= 1000",
            name="ck_household_preparation_resource_capacity",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    calendar_version_id = Column(
        Integer,
        ForeignKey("resource_calendar_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id = Column(String, nullable=False)
    label = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    resource_kind = Column(String, nullable=False)
    availability_windows = Column(JSON, nullable=False)
    resource_metadata = Column(JSON, nullable=False, default=dict)


class DBPersistedPreparationSchedule(Base):
    __tablename__ = "persisted_preparation_schedules"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "creation_idempotency_key",
            name="uq_persisted_schedule_household_creation_idempotency",
        ),
        CheckConstraint(
            "status IN ('draft','approved','invalidated','completed','cancelled')",
            name="ck_persisted_schedule_status",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_persisted_schedule_version_positive",
        ),
        CheckConstraint(
            "length(calendar_content_hash) = 64",
            name="ck_persisted_schedule_calendar_hash_length",
        ),
        CheckConstraint(
            "length(occurrence_set_hash) = 64",
            name="ck_persisted_schedule_occurrence_hash_length",
        ),
        CheckConstraint(
            "length(schedule_hash) = 64",
            name="ck_persisted_schedule_hash_length",
        ),
        CheckConstraint(
            "length(creation_request_fingerprint) = 64",
            name="ck_persisted_schedule_creation_fingerprint_length",
        ),
        CheckConstraint(
            "((schedule_request_payload IS NULL AND schedule_request_hash IS NULL) OR "
            "(schedule_request_payload IS NOT NULL AND length(schedule_request_hash) = 64))",
            name="ck_persisted_schedule_request_provenance_pair",
        ),
        CheckConstraint(
            "((source_plan_id IS NULL AND source_plan_version IS NULL) OR "
            "(source_plan_id IS NOT NULL AND source_plan_version IS NOT NULL))",
            name="ck_persisted_schedule_plan_source_pair",
        ),
        Index(
            "ix_persisted_schedule_household_status_updated",
            "household_id",
            "status",
            "updated_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        String,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    calendar_version_id = Column(
        Integer,
        ForeignKey("resource_calendar_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    calendar_content_hash = Column(String, nullable=False)
    source_plan_id = Column(
        Integer,
        ForeignKey("meal_plans.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    source_plan_version = Column(Integer, nullable=True)
    occurrence_set_version = Column(String, nullable=False)
    occurrence_set_hash = Column(String, nullable=False)
    profile_versions = Column(JSON, nullable=False, default=dict)
    schedule_request_payload = Column(JSON, nullable=True)
    schedule_request_hash = Column(String, nullable=True, index=True)
    schedule_payload = Column(JSON, nullable=False)
    schedule_hash = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False, default=1)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    invalidated_at = Column(DateTime(timezone=True), nullable=True)
    invalidation_reason = Column(Text, nullable=True)
    creation_idempotency_key = Column(String, nullable=False)
    creation_request_fingerprint = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DBPreparationScheduleEvent(Base):
    __tablename__ = "preparation_schedule_events"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "idempotency_key",
            name="uq_preparation_schedule_event_household_idempotency",
        ),
        CheckConstraint(
            "event_type IN ('created','approved','invalidated','completed','cancelled')",
            name="ck_preparation_schedule_event_type",
        ),
        CheckConstraint(
            "to_status IN ('draft','approved','invalidated','completed','cancelled')",
            name="ck_preparation_schedule_event_to_status",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('draft','approved','invalidated','completed','cancelled')",
            name="ck_preparation_schedule_event_from_status",
        ),
        CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_preparation_schedule_event_fingerprint_length",
        ),
        Index(
            "ix_preparation_schedule_event_schedule_created",
            "schedule_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(
        Integer,
        ForeignKey("persisted_preparation_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    household_id = Column(
        String,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String, nullable=False, index=True)
    actor_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    event_metadata = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String, nullable=False)
    request_fingerprint = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
