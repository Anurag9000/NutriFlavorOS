"""Add append-only user-confirmed preparation task execution events.

Revision ID: 20260802_0014
Revises: 20260802_0013
Create Date: 2026-08-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260802_0014"
down_revision = "20260802_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preparation_task_execution_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "schedule_id",
            sa.Integer(),
            sa.ForeignKey("persisted_preparation_schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.String(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(length=32), nullable=False),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("planned_start_minute", sa.Integer(), nullable=False),
        sa.Column("planned_finish_minute", sa.Integer(), nullable=False),
        sa.Column("actual_minute", sa.Integer(), nullable=False),
        sa.Column("deviation_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("schedule_version_before", sa.Integer(), nullable=False),
        sa.Column("schedule_version_after", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "schedule_id",
            "idempotency_key",
            name="uq_preparation_task_event_schedule_idempotency",
        ),
        sa.CheckConstraint(
            "length(trim(task_id)) > 0",
            name="ck_preparation_task_event_task_nonblank",
        ),
        sa.CheckConstraint(
            "event_type IN ('started','completed','skipped')",
            name="ck_preparation_task_event_type",
        ),
        sa.CheckConstraint(
            "from_state IN ('planned','in_progress')",
            name="ck_preparation_task_event_from_state",
        ),
        sa.CheckConstraint(
            "to_state IN ('in_progress','completed','skipped')",
            name="ck_preparation_task_event_to_state",
        ),
        sa.CheckConstraint(
            "(event_type = 'started' AND from_state = 'planned' "
            "AND to_state = 'in_progress') OR "
            "(event_type = 'completed' AND from_state = 'in_progress' "
            "AND to_state = 'completed') OR "
            "(event_type = 'skipped' AND from_state IN ('planned','in_progress') "
            "AND to_state = 'skipped')",
            name="ck_preparation_task_event_transition",
        ),
        sa.CheckConstraint(
            "planned_start_minute >= 0 AND planned_start_minute <= 10080 "
            "AND planned_finish_minute > planned_start_minute "
            "AND planned_finish_minute <= 10080",
            name="ck_preparation_task_event_planned_bounds",
        ),
        sa.CheckConstraint(
            "actual_minute >= 0 AND actual_minute <= 10080",
            name="ck_preparation_task_event_actual_bounds",
        ),
        sa.CheckConstraint(
            "(event_type = 'started' "
            "AND deviation_minutes = actual_minute - planned_start_minute) OR "
            "(event_type = 'completed' "
            "AND deviation_minutes = actual_minute - planned_finish_minute) OR "
            "(event_type = 'skipped' AND deviation_minutes = 0)",
            name="ck_preparation_task_event_deviation",
        ),
        sa.CheckConstraint(
            "((event_type = 'skipped' OR deviation_minutes <> 0) "
            "AND reason IS NOT NULL AND length(trim(reason)) > 0) OR "
            "(event_type IN ('started','completed') AND deviation_minutes = 0)",
            name="ck_preparation_task_event_reason_required",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_preparation_task_event_fingerprint_length",
        ),
        sa.CheckConstraint(
            "schedule_version_before >= 1 "
            "AND schedule_version_after = schedule_version_before + 1",
            name="ck_preparation_task_event_schedule_versions",
        ),
    )
    op.create_index(
        "ix_preparation_task_events_schedule_created",
        "preparation_task_execution_events",
        ["schedule_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_task_events_schedule_task_created",
        "preparation_task_execution_events",
        ["schedule_id", "task_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_task_events_household_created",
        "preparation_task_execution_events",
        ["household_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preparation_task_events_household_created",
        table_name="preparation_task_execution_events",
    )
    op.drop_index(
        "ix_preparation_task_events_schedule_task_created",
        table_name="preparation_task_execution_events",
    )
    op.drop_index(
        "ix_preparation_task_events_schedule_created",
        table_name="preparation_task_execution_events",
    )
    op.drop_table("preparation_task_execution_events")
