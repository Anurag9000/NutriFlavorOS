"""Add immutable resource calendars and persisted preparation schedules.

Revision ID: 20260801_0009
Revises: 20260801_0008
Create Date: 2026-08-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260801_0009"
down_revision = "20260801_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resource_calendar_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("household_id", sa.String(), nullable=False),
        sa.Column("calendar_version", sa.String(), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("evidence_status", sa.String(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("supersedes_calendar_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_status IN ('draft','reviewed')",
            name="ck_resource_calendar_evidence_status",
        ),
        sa.CheckConstraint(
            "horizon_minutes >= 1 AND horizon_minutes <= 10080",
            name="ck_resource_calendar_horizon",
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_resource_calendar_hash_length",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_resource_calendar_request_fingerprint_length",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_resource_calendar_household",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_calendar_id"],
            ["resource_calendar_versions.id"],
            name="fk_resource_calendar_supersedes",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_resource_calendar_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "calendar_version",
            name="uq_resource_calendar_household_version",
        ),
        sa.UniqueConstraint(
            "household_id",
            "idempotency_key",
            name="uq_resource_calendar_household_idempotency",
        ),
    )
    op.create_index(
        "ix_resource_calendar_versions_household_id",
        "resource_calendar_versions",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_resource_calendar_versions_evidence_status",
        "resource_calendar_versions",
        ["evidence_status"],
        unique=False,
    )
    op.create_index(
        "ix_resource_calendar_versions_content_hash",
        "resource_calendar_versions",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_resource_calendar_versions_active",
        "resource_calendar_versions",
        ["active"],
        unique=False,
    )
    op.create_index(
        "ix_resource_calendar_versions_request_fingerprint",
        "resource_calendar_versions",
        ["request_fingerprint"],
        unique=False,
    )
    op.create_index(
        "uq_active_reviewed_resource_calendar_household",
        "resource_calendar_versions",
        ["household_id"],
        unique=True,
        sqlite_where=sa.text(
            "active = 1 AND evidence_status = 'reviewed'"
        ),
        postgresql_where=sa.text(
            "active IS TRUE AND evidence_status = 'reviewed'"
        ),
    )

    op.create_table(
        "household_preparation_resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("calendar_version_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("resource_kind", sa.String(), nullable=False),
        sa.Column("availability_windows", sa.JSON(), nullable=False),
        sa.Column("resource_metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "capacity >= 1 AND capacity <= 1000",
            name="ck_household_preparation_resource_capacity",
        ),
        sa.ForeignKeyConstraint(
            ["calendar_version_id"],
            ["resource_calendar_versions.id"],
            name="fk_household_preparation_resource_calendar",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "calendar_version_id",
            "resource_id",
            name="uq_household_preparation_resource_calendar_key",
        ),
    )
    op.create_index(
        "ix_household_preparation_resources_calendar_version_id",
        "household_preparation_resources",
        ["calendar_version_id"],
        unique=False,
    )

    op.create_table(
        "persisted_preparation_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("household_id", sa.String(), nullable=False),
        sa.Column("calendar_version_id", sa.Integer(), nullable=False),
        sa.Column("calendar_content_hash", sa.String(), nullable=False),
        sa.Column("source_plan_id", sa.Integer(), nullable=True),
        sa.Column("source_plan_version", sa.Integer(), nullable=True),
        sa.Column("occurrence_set_version", sa.String(), nullable=False),
        sa.Column("occurrence_set_hash", sa.String(), nullable=False),
        sa.Column("profile_versions", sa.JSON(), nullable=False),
        sa.Column("schedule_payload", sa.JSON(), nullable=False),
        sa.Column("schedule_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("approved_by_user_id", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column("creation_idempotency_key", sa.String(), nullable=False),
        sa.Column("creation_request_fingerprint", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','approved','invalidated','completed','cancelled')",
            name="ck_persisted_schedule_status",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_persisted_schedule_version_positive",
        ),
        sa.CheckConstraint(
            "length(calendar_content_hash) = 64",
            name="ck_persisted_schedule_calendar_hash_length",
        ),
        sa.CheckConstraint(
            "length(occurrence_set_hash) = 64",
            name="ck_persisted_schedule_occurrence_hash_length",
        ),
        sa.CheckConstraint(
            "length(schedule_hash) = 64",
            name="ck_persisted_schedule_hash_length",
        ),
        sa.CheckConstraint(
            "length(creation_request_fingerprint) = 64",
            name="ck_persisted_schedule_creation_fingerprint_length",
        ),
        sa.CheckConstraint(
            "((source_plan_id IS NULL AND source_plan_version IS NULL) OR "
            "(source_plan_id IS NOT NULL AND source_plan_version IS NOT NULL))",
            name="ck_persisted_schedule_plan_source_pair",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_persisted_schedule_household",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["calendar_version_id"],
            ["resource_calendar_versions.id"],
            name="fk_persisted_schedule_calendar",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_plan_id"],
            ["meal_plans.id"],
            name="fk_persisted_schedule_source_plan",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_persisted_schedule_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name="fk_persisted_schedule_approver",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "creation_idempotency_key",
            name="uq_persisted_schedule_household_creation_idempotency",
        ),
    )
    op.create_index(
        "ix_persisted_preparation_schedules_household_id",
        "persisted_preparation_schedules",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_persisted_preparation_schedules_calendar_version_id",
        "persisted_preparation_schedules",
        ["calendar_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_persisted_preparation_schedules_source_plan_id",
        "persisted_preparation_schedules",
        ["source_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_persisted_preparation_schedules_schedule_hash",
        "persisted_preparation_schedules",
        ["schedule_hash"],
        unique=False,
    )
    op.create_index(
        "ix_persisted_preparation_schedules_status",
        "persisted_preparation_schedules",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_persisted_preparation_schedules_creation_request_fingerprint",
        "persisted_preparation_schedules",
        ["creation_request_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_persisted_schedule_household_status_updated",
        "persisted_preparation_schedules",
        ["household_id", "status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "preparation_schedule_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('created','approved','invalidated','completed','cancelled')",
            name="ck_preparation_schedule_event_type",
        ),
        sa.CheckConstraint(
            "to_status IN ('draft','approved','invalidated','completed','cancelled')",
            name="ck_preparation_schedule_event_to_status",
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('draft','approved','invalidated','completed','cancelled')",
            name="ck_preparation_schedule_event_from_status",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_preparation_schedule_event_fingerprint_length",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["persisted_preparation_schedules.id"],
            name="fk_preparation_schedule_event_schedule",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_preparation_schedule_event_household",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_preparation_schedule_event_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "idempotency_key",
            name="uq_preparation_schedule_event_household_idempotency",
        ),
    )
    op.create_index(
        "ix_preparation_schedule_events_schedule_id",
        "preparation_schedule_events",
        ["schedule_id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_schedule_events_household_id",
        "preparation_schedule_events",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_schedule_events_event_type",
        "preparation_schedule_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_schedule_events_request_fingerprint",
        "preparation_schedule_events",
        ["request_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_schedule_event_schedule_created",
        "preparation_schedule_events",
        ["schedule_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("preparation_schedule_events")
    op.drop_table("persisted_preparation_schedules")
    op.drop_table("household_preparation_resources")
    op.drop_index(
        "uq_active_reviewed_resource_calendar_household",
        table_name="resource_calendar_versions",
    )
    op.drop_table("resource_calendar_versions")
