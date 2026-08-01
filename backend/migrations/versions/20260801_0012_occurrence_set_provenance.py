"""Persist verified household preparation occurrence documents.

Revision ID: 20260801_0012
Revises: 20260801_0011
Create Date: 2026-08-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260801_0012"
down_revision = "20260801_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("persisted_preparation_schedules") as batch_op:
        batch_op.add_column(
            sa.Column("occurrence_set_payload", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("persisted_preparation_schedules") as batch_op:
        batch_op.drop_column("occurrence_set_payload")
