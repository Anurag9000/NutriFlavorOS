"""Add optimistic household-plan approval lifecycle and transition events.

Revision ID: 20260802_0013
Revises: 20260801_0012
Create Date: 2026-08-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260802_0013"
down_revision = "20260801_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("meal_plans") as batch_op:
        batch_op.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="draft",
            )
        )
        batch_op.add_column(
            sa.Column("approved_by_user_id", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cancellation_reason", sa.String(length=1000), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch_op.create_foreign_key(
            "fk_meal_plans_approved_by_user",
            "users",
            ["approved_by_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            "ck_meal_plan_version_positive",
            "version >= 1",
        )
        batch_op.create_check_constraint(
            "ck_meal_plan_valid_status",
            "status IN ('draft','approved','cancelled')",
        )
        batch_op.create_check_constraint(
            "ck_meal_plan_approval_pair",
            "((approved_by_user_id IS NULL AND approved_at IS NULL) OR "
            "(approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL))",
        )
        batch_op.create_check_constraint(
            "ck_meal_plan_state_fields",
            "(status = 'draft' AND approved_by_user_id IS NULL "
            "AND approved_at IS NULL AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) OR "
            "(status = 'approved' AND approved_by_user_id IS NOT NULL "
            "AND approved_at IS NOT NULL AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL "
            "AND cancellation_reason IS NOT NULL)",
        )

    op.create_index(
        "ix_meal_plans_household_status_created",
        "meal_plans",
        ["household_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "household_plan_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("meal_plans.id", ondelete="CASCADE"),
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
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "plan_id",
            "idempotency_key",
            name="uq_household_plan_event_idempotency",
        ),
        sa.CheckConstraint(
            "event_type IN ('approved','cancelled')",
            name="ck_household_plan_event_type",
        ),
        sa.CheckConstraint(
            "from_status IN ('draft','approved')",
            name="ck_household_plan_event_from_status",
        ),
        sa.CheckConstraint(
            "to_status IN ('approved','cancelled')",
            name="ck_household_plan_event_to_status",
        ),
        sa.CheckConstraint(
            "(event_type = 'approved' AND from_status = 'draft' "
            "AND to_status = 'approved') OR "
            "(event_type = 'cancelled' AND from_status IN ('draft','approved') "
            "AND to_status = 'cancelled')",
            name="ck_household_plan_event_transition",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_household_plan_event_reason_nonblank",
        ),
    )
    op.create_index(
        "ix_household_plan_events_plan_created",
        "household_plan_events",
        ["plan_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_household_plan_events_household_created",
        "household_plan_events",
        ["household_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_household_plan_events_household_created",
        table_name="household_plan_events",
    )
    op.drop_index(
        "ix_household_plan_events_plan_created",
        table_name="household_plan_events",
    )
    op.drop_table("household_plan_events")
    op.drop_index(
        "ix_meal_plans_household_status_created",
        table_name="meal_plans",
    )
    with op.batch_alter_table("meal_plans") as batch_op:
        batch_op.drop_constraint(
            "ck_meal_plan_state_fields",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_meal_plan_approval_pair",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_meal_plan_valid_status",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_meal_plan_version_positive",
            type_="check",
        )
        batch_op.drop_constraint(
            "fk_meal_plans_approved_by_user",
            type_="foreignkey",
        )
        batch_op.drop_column("updated_at")
        batch_op.drop_column("cancellation_reason")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("approved_by_user_id")
        batch_op.drop_column("status")
        batch_op.drop_column("version")
