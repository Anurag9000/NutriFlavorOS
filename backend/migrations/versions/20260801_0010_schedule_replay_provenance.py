"""Persist complete schedule replay inputs and request hashes.

Revision ID: 20260801_0010
Revises: 20260801_0009
Create Date: 2026-08-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260801_0010"
down_revision = "20260801_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("persisted_preparation_schedules") as batch_op:
        batch_op.add_column(
            sa.Column("schedule_request_payload", sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("schedule_request_hash", sa.String(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_persisted_schedule_request_provenance_pair",
            "((schedule_request_payload IS NULL AND schedule_request_hash IS NULL) OR "
            "(schedule_request_payload IS NOT NULL AND length(schedule_request_hash) = 64))",
        )
        batch_op.create_index(
            "ix_persisted_preparation_schedules_schedule_request_hash",
            ["schedule_request_hash"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("persisted_preparation_schedules") as batch_op:
        batch_op.drop_index(
            "ix_persisted_preparation_schedules_schedule_request_hash"
        )
        batch_op.drop_constraint(
            "ck_persisted_schedule_request_provenance_pair",
            type_="check",
        )
        batch_op.drop_column("schedule_request_hash")
        batch_op.drop_column("schedule_request_payload")
