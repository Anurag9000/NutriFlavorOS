"""Add append-only lifecycle events for immutable food evidence.

Revision ID: 20260801_0008
Revises: 20260801_0007
Create Date: 2026-08-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260801_0008"
down_revision = "20260801_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_lifecycle_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_kind", sa.String(), nullable=False),
        sa.Column("conversion_version_id", sa.Integer(), nullable=True),
        sa.Column("storage_policy_version_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(), nullable=False),
        sa.Column("target_was_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "evidence_kind IN ('conversion','storage_policy')",
            name="ck_evidence_lifecycle_kind",
        ),
        sa.CheckConstraint(
            "action IN ('deactivated','rejected')",
            name="ck_evidence_lifecycle_action",
        ),
        sa.CheckConstraint(
            "((conversion_version_id IS NOT NULL AND storage_policy_version_id IS NULL) "
            "OR (conversion_version_id IS NULL AND storage_policy_version_id IS NOT NULL))",
            name="ck_evidence_lifecycle_exactly_one_target",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_evidence_lifecycle_fingerprint_length",
        ),
        sa.ForeignKeyConstraint(
            ["conversion_version_id"],
            ["ingredient_conversion_versions.id"],
            name="fk_evidence_lifecycle_conversion",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["storage_policy_version_id"],
            ["storage_policy_versions.id"],
            name="fk_evidence_lifecycle_policy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_evidence_lifecycle_idempotency_key",
        ),
    )
    op.create_index(
        "ix_evidence_lifecycle_events_evidence_kind",
        "evidence_lifecycle_events",
        ["evidence_kind"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_lifecycle_events_action",
        "evidence_lifecycle_events",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_lifecycle_events_request_fingerprint",
        "evidence_lifecycle_events",
        ["request_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_lifecycle_conversion_created",
        "evidence_lifecycle_events",
        ["conversion_version_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_lifecycle_policy_created",
        "evidence_lifecycle_events",
        ["storage_policy_version_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evidence_lifecycle_policy_created",
        table_name="evidence_lifecycle_events",
    )
    op.drop_index(
        "ix_evidence_lifecycle_conversion_created",
        table_name="evidence_lifecycle_events",
    )
    op.drop_index(
        "ix_evidence_lifecycle_events_request_fingerprint",
        table_name="evidence_lifecycle_events",
    )
    op.drop_index(
        "ix_evidence_lifecycle_events_action",
        table_name="evidence_lifecycle_events",
    )
    op.drop_index(
        "ix_evidence_lifecycle_events_evidence_kind",
        table_name="evidence_lifecycle_events",
    )
    op.drop_table("evidence_lifecycle_events")
