"""Create the versioned foundational schema and upgrade prototype databases.

Revision ID: 20260731_0001
Revises: None
Create Date: 2026-07-31
"""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260731_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _add_missing_columns(table_name: str, columns: Iterable[Tuple[str, sa.Column]]) -> None:
    existing = _column_names(table_name)
    for name, column in columns:
        if name not in existing:
            op.add_column(table_name, column)


def _drop_existing_columns(table_name: str, names: Iterable[str]) -> None:
    existing = _column_names(table_name)
    with op.batch_alter_table(table_name) as batch:
        for name in names:
            if name in existing:
                batch.drop_column(name)


def _ensure_index(table: str, name: str, columns: list[str]) -> None:
    if name not in _index_names(table):
        op.create_index(name, table, columns)


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("gender", sa.String(), nullable=True),
        sa.Column("activity_level", sa.Float(), nullable=True),
        sa.Column("goal", sa.String(), nullable=True),
        sa.Column("liked_ingredients", sa.JSON(), nullable=False),
        sa.Column("disliked_ingredients", sa.JSON(), nullable=False),
        sa.Column("allergies", sa.JSON(), nullable=False),
        sa.Column("dietary_restrictions", sa.JSON(), nullable=False),
        sa.Column("health_conditions", sa.JSON(), nullable=False),
        sa.Column("medications", sa.JSON(), nullable=False),
        sa.Column("target_calories", sa.Integer(), nullable=True),
        sa.Column("target_protein_g", sa.Integer(), nullable=True),
        sa.Column("target_carbs_g", sa.Integer(), nullable=True),
        sa.Column("target_fat_g", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    _ensure_index("users", "ix_users_id", ["id"])


def _create_recipes() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("ingredients", sa.JSON(), nullable=False),
        sa.Column("ingredient_data", sa.JSON(), nullable=False),
        sa.Column("servings", sa.Float(), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=False),
        sa.Column("macros", sa.JSON(), nullable=False),
        sa.Column("flavor_profile", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("cuisine", sa.String(), nullable=True),
        sa.Column("instructions", sa.JSON(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source_version", sa.String(), nullable=True),
        sa.Column("nutrition_basis", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _ensure_index("recipes", "ix_recipes_id", ["id"])
    _ensure_index("recipes", "ix_recipes_name", ["name"])


def _create_meal_plans() -> None:
    op.create_table(
        "meal_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("plan_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _ensure_index("meal_plans", "ix_meal_plans_id", ["id"])
    _ensure_index("meal_plans", "ix_meal_plans_user_id", ["user_id"])
    _ensure_index("meal_plans", "ix_meal_plans_created_at", ["created_at"])


def upgrade() -> None:
    tables = _table_names()

    if "users" not in tables:
        _create_users()
    else:
        _add_missing_columns(
            "users",
            (
                ("hashed_password", sa.Column("hashed_password", sa.String(), nullable=True)),
                ("allergies", sa.Column("allergies", sa.JSON(), nullable=True)),
                ("medications", sa.Column("medications", sa.JSON(), nullable=True)),
                ("target_calories", sa.Column("target_calories", sa.Integer(), nullable=True)),
                ("target_protein_g", sa.Column("target_protein_g", sa.Integer(), nullable=True)),
                ("target_carbs_g", sa.Column("target_carbs_g", sa.Integer(), nullable=True)),
                ("target_fat_g", sa.Column("target_fat_g", sa.Integer(), nullable=True)),
            ),
        )
        users = sa.table(
            "users",
            sa.column("allergies", sa.JSON()),
            sa.column("medications", sa.JSON()),
        )
        op.execute(users.update().where(users.c.allergies.is_(None)).values(allergies=[]))
        op.execute(users.update().where(users.c.medications.is_(None)).values(medications=[]))
        with op.batch_alter_table("users") as batch:
            batch.alter_column("allergies", existing_type=sa.JSON(), nullable=False)
            batch.alter_column("medications", existing_type=sa.JSON(), nullable=False)

    tables = _table_names()
    if "recipes" not in tables:
        _create_recipes()
    else:
        _add_missing_columns(
            "recipes",
            (
                ("ingredient_data", sa.Column("ingredient_data", sa.JSON(), nullable=True)),
                ("servings", sa.Column("servings", sa.Float(), nullable=True)),
                ("source_name", sa.Column("source_name", sa.String(), nullable=True)),
                ("source_url", sa.Column("source_url", sa.String(), nullable=True)),
                ("source_version", sa.Column("source_version", sa.String(), nullable=True)),
                ("nutrition_basis", sa.Column("nutrition_basis", sa.String(), nullable=True)),
            ),
        )
        recipes = sa.table(
            "recipes",
            sa.column("ingredient_data", sa.JSON()),
            sa.column("servings", sa.Float()),
            sa.column("nutrition_basis", sa.String()),
        )
        op.execute(recipes.update().where(recipes.c.ingredient_data.is_(None)).values(ingredient_data=[]))
        op.execute(recipes.update().where(sa.or_(recipes.c.servings.is_(None), recipes.c.servings <= 0)).values(servings=1.0))
        op.execute(recipes.update().where(recipes.c.nutrition_basis.is_(None)).values(nutrition_basis="per_serving"))
        with op.batch_alter_table("recipes") as batch:
            batch.alter_column("ingredient_data", existing_type=sa.JSON(), nullable=False)
            batch.alter_column("servings", existing_type=sa.Float(), nullable=False)
            batch.alter_column("nutrition_basis", existing_type=sa.String(), nullable=False)

    tables = _table_names()
    if "meal_plans" not in tables:
        _create_meal_plans()
    else:
        _add_missing_columns(
            "meal_plans",
            (("schema_version", sa.Column("schema_version", sa.String(), nullable=True)),),
        )
        plans = sa.table("meal_plans", sa.column("schema_version", sa.String()))
        op.execute(plans.update().where(plans.c.schema_version.is_(None)).values(schema_version="2"))
        with op.batch_alter_table("meal_plans") as batch:
            batch.alter_column("schema_version", existing_type=sa.String(), nullable=False)

    if "feedback_events" not in _table_names():
        op.create_table(
            "feedback_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("feedback_type", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    _ensure_index("feedback_events", "ix_feedback_events_user_id", ["user_id"])
    _ensure_index("feedback_events", "ix_feedback_events_feedback_type", ["feedback_type"])
    _ensure_index("feedback_events", "ix_feedback_events_created_at", ["created_at"])


def downgrade() -> None:
    tables = _table_names()
    if "feedback_events" in tables:
        op.drop_table("feedback_events")
    if "meal_plans" in tables:
        _drop_existing_columns("meal_plans", ("schema_version",))
    if "recipes" in tables:
        _drop_existing_columns(
            "recipes",
            ("ingredient_data", "servings", "source_name", "source_url", "source_version", "nutrition_basis"),
        )
    if "users" in tables:
        _drop_existing_columns(
            "users",
            (
                "hashed_password",
                "allergies",
                "medications",
                "target_calories",
                "target_protein_g",
                "target_carbs_g",
                "target_fat_g",
            ),
        )
