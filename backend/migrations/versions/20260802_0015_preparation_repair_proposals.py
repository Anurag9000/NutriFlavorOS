"""Add immutable server-recomputed preparation repair proposals.

Revision ID: 20260802_0015
Revises: 20260802_0014
Create Date: 2026-08-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260802_0015"
down_revision = "20260802_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preparation_repair_proposals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "household_id",
            sa.String(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_schedule_id",
            sa.Integer(),
            sa.ForeignKey("persisted_preparation_schedules.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_schedule_version", sa.Integer(), nullable=False),
        sa.Column("source_schedule_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "source_schedule_request_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "target_calendar_version_id",
            sa.Integer(),
            sa.ForeignKey("resource_calendar_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "target_calendar_content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("repair_request_payload", sa.JSON(), nullable=False),
        sa.Column("repair_request_hash", sa.String(length=64), nullable=False),
        sa.Column("repair_result_payload", sa.JSON(), nullable=False),
        sa.Column("repair_result_hash", sa.String(length=64), nullable=False),
        sa.Column("revised_request_hash", sa.String(length=64), nullable=False),
        sa.Column("repaired_response_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "required_acknowledgement_task_ids",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "rejected_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("creation_idempotency_key", sa.String(length=240), nullable=False),
        sa.Column(
            "creation_request_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "household_id",
            "creation_idempotency_key",
            name="uq_preparation_repair_proposal_household_idempotency",
        ),
        sa.UniqueConstraint(
            "source_schedule_id",
            "source_schedule_version",
            "revised_request_hash",
            "repaired_response_hash",
            name="uq_preparation_repair_proposal_semantic_identity",
        ),
        sa.CheckConstraint(
            "status IN ('proposed','rejected','invalidated')",
            name="ck_preparation_repair_proposal_status",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_preparation_repair_proposal_version_positive",
        ),
        sa.CheckConstraint(
            "length(source_schedule_hash) = 64",
            name="ck_preparation_repair_proposal_source_hash_length",
        ),
        sa.CheckConstraint(
            "length(source_schedule_request_hash) = 64",
            name="ck_preparation_repair_proposal_source_request_hash_length",
        ),
        sa.CheckConstraint(
            "length(target_calendar_content_hash) = 64",
            name="ck_preparation_repair_proposal_calendar_hash_length",
        ),
        sa.CheckConstraint(
            "length(repair_request_hash) = 64",
            name="ck_preparation_repair_proposal_request_hash_length",
        ),
        sa.CheckConstraint(
            "length(repair_result_hash) = 64",
            name="ck_preparation_repair_proposal_result_hash_length",
        ),
        sa.CheckConstraint(
            "length(revised_request_hash) = 64",
            name="ck_preparation_repair_proposal_revised_hash_length",
        ),
        sa.CheckConstraint(
            "length(repaired_response_hash) = 64",
            name="ck_preparation_repair_proposal_response_hash_length",
        ),
        sa.CheckConstraint(
            "length(creation_request_fingerprint) = 64",
            name="ck_preparation_repair_proposal_fingerprint_length",
        ),
        sa.CheckConstraint(
            "((status = 'rejected' AND rejected_by_user_id IS NOT NULL "
            "AND rejected_at IS NOT NULL AND rejection_reason IS NOT NULL "
            "AND length(trim(rejection_reason)) > 0) OR "
            "(status <> 'rejected' AND rejected_by_user_id IS NULL "
            "AND rejected_at IS NULL AND rejection_reason IS NULL))",
            name="ck_preparation_repair_proposal_rejection_state",
        ),
    )
    op.create_index(
        "ix_preparation_repair_proposals_household_status_updated",
        "preparation_repair_proposals",
        ["household_id", "status", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposals_source_schedule",
        "preparation_repair_proposals",
        ["source_schedule_id", "source_schedule_version"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposals_repair_request_hash",
        "preparation_repair_proposals",
        ["repair_request_hash"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposals_repair_result_hash",
        "preparation_repair_proposals",
        ["repair_result_hash"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposals_revised_request_hash",
        "preparation_repair_proposals",
        ["revised_request_hash"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposals_repaired_response_hash",
        "preparation_repair_proposals",
        ["repaired_response_hash"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposals_creation_fingerprint",
        "preparation_repair_proposals",
        ["creation_request_fingerprint"],
        unique=False,
    )

    op.create_table(
        "preparation_repair_proposal_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "proposal_id",
            sa.Integer(),
            sa.ForeignKey("preparation_repair_proposals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.String(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("proposal_version_before", sa.Integer(), nullable=False),
        sa.Column("proposal_version_after", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "proposal_id",
            "idempotency_key",
            name="uq_preparation_repair_event_proposal_idempotency",
        ),
        sa.CheckConstraint(
            "event_type IN ('created','rejected','invalidated')",
            name="ck_preparation_repair_event_type",
        ),
        sa.CheckConstraint(
            "to_status IN ('proposed','rejected','invalidated')",
            name="ck_preparation_repair_event_to_status",
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('proposed','rejected','invalidated')",
            name="ck_preparation_repair_event_from_status",
        ),
        sa.CheckConstraint(
            "((event_type = 'created' AND from_status IS NULL "
            "AND to_status = 'proposed') OR "
            "(event_type = 'rejected' AND from_status = 'proposed' "
            "AND to_status = 'rejected') OR "
            "(event_type = 'invalidated' AND from_status = 'proposed' "
            "AND to_status = 'invalidated'))",
            name="ck_preparation_repair_event_transition",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_preparation_repair_event_reason_nonblank",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_preparation_repair_event_fingerprint_length",
        ),
        sa.CheckConstraint(
            "proposal_version_before >= 0 "
            "AND proposal_version_after = proposal_version_before + 1",
            name="ck_preparation_repair_event_versions",
        ),
    )
    op.create_index(
        "ix_preparation_repair_events_proposal_created",
        "preparation_repair_proposal_events",
        ["proposal_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_events_household_created",
        "preparation_repair_proposal_events",
        ["household_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_events_request_fingerprint",
        "preparation_repair_proposal_events",
        ["request_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preparation_repair_events_request_fingerprint",
        table_name="preparation_repair_proposal_events",
    )
    op.drop_index(
        "ix_preparation_repair_events_household_created",
        table_name="preparation_repair_proposal_events",
    )
    op.drop_index(
        "ix_preparation_repair_events_proposal_created",
        table_name="preparation_repair_proposal_events",
    )
    op.drop_table("preparation_repair_proposal_events")

    op.drop_index(
        "ix_preparation_repair_proposals_creation_fingerprint",
        table_name="preparation_repair_proposals",
    )
    op.drop_index(
        "ix_preparation_repair_proposals_repaired_response_hash",
        table_name="preparation_repair_proposals",
    )
    op.drop_index(
        "ix_preparation_repair_proposals_revised_request_hash",
        table_name="preparation_repair_proposals",
    )
    op.drop_index(
        "ix_preparation_repair_proposals_repair_result_hash",
        table_name="preparation_repair_proposals",
    )
    op.drop_index(
        "ix_preparation_repair_proposals_repair_request_hash",
        table_name="preparation_repair_proposals",
    )
    op.drop_index(
        "ix_preparation_repair_proposals_source_schedule",
        table_name="preparation_repair_proposals",
    )
    op.drop_index(
        "ix_preparation_repair_proposals_household_status_updated",
        table_name="preparation_repair_proposals",
    )
    op.drop_table("preparation_repair_proposals")
