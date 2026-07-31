"""Add reviewed recipe preparation evidence profiles.

Revision ID: 20260731_0005
Revises: 20260731_0004
Create Date: 2026-07-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260731_0005"
down_revision: Union[str, None] = "20260731_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "recipe_preparation_profiles" in _tables():
        return
    op.create_table(
        "recipe_preparation_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recipe_id", sa.String(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("supported_servings_min", sa.Float(), nullable=False),
        sa.Column("supported_servings_max", sa.Float(), nullable=False),
        sa.Column("task_templates", sa.JSON(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("source_version", sa.String(), nullable=False),
        sa.Column("evidence_status", sa.String(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_status IN ('draft','external_unverified','reviewed')",
            name="ck_recipe_preparation_profile_status",
        ),
        sa.CheckConstraint(
            "schema_version <> ''",
            name="ck_recipe_preparation_profile_schema_version",
        ),
        sa.CheckConstraint(
            "supported_servings_min > 0",
            name="ck_recipe_preparation_profile_servings_min",
        ),
        sa.CheckConstraint(
            "supported_servings_max >= supported_servings_min",
            name="ck_recipe_preparation_profile_servings_range",
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipe_id",
            name="uq_recipe_preparation_profile_recipe",
        ),
    )
    op.create_index(
        "ix_recipe_preparation_profiles_recipe_id",
        "recipe_preparation_profiles",
        ["recipe_id"],
    )
    op.create_index(
        "ix_recipe_preparation_profiles_evidence_status",
        "recipe_preparation_profiles",
        ["evidence_status"],
    )
    op.create_index(
        "ix_recipe_preparation_profiles_active",
        "recipe_preparation_profiles",
        ["active"],
    )


def downgrade() -> None:
    if "recipe_preparation_profiles" in _tables():
        op.drop_table("recipe_preparation_profiles")
