"""Enforce calendar, schedule, and event lifecycle state consistency.

Revision ID: 20260801_0011
Revises: 20260801_0010
Create Date: 2026-08-01
"""

from __future__ import annotations

from alembic import op


revision = "20260801_0011"
down_revision = "20260801_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("resource_calendar_versions") as batch_op:
        batch_op.create_check_constraint(
            "ck_resource_calendar_review_state",
            "((evidence_status = 'reviewed' AND reviewed_at IS NOT NULL "
            "AND reviewed_by IS NOT NULL AND length(trim(reviewed_by)) > 0) OR "
            "(evidence_status = 'draft' AND NOT active))",
        )
        batch_op.create_check_constraint(
            "ck_resource_calendar_active_reviewed",
            "NOT active OR evidence_status = 'reviewed'",
        )

    with op.batch_alter_table("persisted_preparation_schedules") as batch_op:
        batch_op.create_check_constraint(
            "ck_persisted_schedule_approval_state",
            "((status IN ('approved','completed') AND approved_by_user_id IS NOT NULL "
            "AND approved_at IS NOT NULL) OR status NOT IN ('approved','completed'))",
        )
        batch_op.create_check_constraint(
            "ck_persisted_schedule_invalidation_state",
            "((status = 'invalidated' AND invalidated_at IS NOT NULL "
            "AND invalidation_reason IS NOT NULL "
            "AND length(trim(invalidation_reason)) > 0) OR "
            "(status <> 'invalidated' AND invalidated_at IS NULL "
            "AND invalidation_reason IS NULL))",
        )

    with op.batch_alter_table("preparation_schedule_events") as batch_op:
        batch_op.create_check_constraint(
            "ck_preparation_schedule_event_transition_pair",
            "((event_type = 'created' AND from_status IS NULL AND to_status = 'draft') OR "
            "(event_type = 'approved' AND from_status = 'draft' AND to_status = 'approved') OR "
            "(event_type = 'completed' AND from_status = 'approved' AND to_status = 'completed') OR "
            "(event_type = 'cancelled' AND from_status IN ('draft','approved') "
            "AND to_status = 'cancelled') OR "
            "(event_type = 'invalidated' AND from_status IN ('draft','approved') "
            "AND to_status = 'invalidated'))",
        )
        batch_op.create_check_constraint(
            "ck_preparation_schedule_event_reason_nonblank",
            "length(trim(reason)) > 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("preparation_schedule_events") as batch_op:
        batch_op.drop_constraint(
            "ck_preparation_schedule_event_reason_nonblank",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_preparation_schedule_event_transition_pair",
            type_="check",
        )

    with op.batch_alter_table("persisted_preparation_schedules") as batch_op:
        batch_op.drop_constraint(
            "ck_persisted_schedule_invalidation_state",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_persisted_schedule_approval_state",
            type_="check",
        )

    with op.batch_alter_table("resource_calendar_versions") as batch_op:
        batch_op.drop_constraint(
            "ck_resource_calendar_active_reviewed",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_resource_calendar_review_state",
            type_="check",
        )
