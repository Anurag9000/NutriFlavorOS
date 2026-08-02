"""Allow only one accepted repair replacement per source schedule version.

Revision ID: 20260802_0018
Revises: 20260802_0017
Create Date: 2026-08-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260802_0018"
down_revision = "20260802_0017"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "uq_preparation_repair_acceptance_source_version"


def _assert_no_duplicate_source_acceptances() -> None:
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            """
            SELECT source_schedule_id,
                   source_schedule_version,
                   COUNT(*) AS acceptance_count
            FROM preparation_repair_proposal_acceptances
            GROUP BY source_schedule_id, source_schedule_version
            HAVING COUNT(*) > 1
            ORDER BY source_schedule_id, source_schedule_version
            """
        )
    ).mappings().all()
    if duplicates:
        formatted = ", ".join(
            (
                f"schedule={row['source_schedule_id']} "
                f"version={row['source_schedule_version']} "
                f"acceptances={row['acceptance_count']}"
            )
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot add one-replacement-per-source constraint while duplicate "
            f"repair acceptances exist: {formatted}"
        )


def upgrade() -> None:
    _assert_no_duplicate_source_acceptances()
    with op.batch_alter_table("preparation_repair_proposal_acceptances") as batch:
        batch.create_unique_constraint(
            CONSTRAINT_NAME,
            ["source_schedule_id", "source_schedule_version"],
        )


def downgrade() -> None:
    with op.batch_alter_table("preparation_repair_proposal_acceptances") as batch:
        batch.drop_constraint(CONSTRAINT_NAME, type_="unique")
