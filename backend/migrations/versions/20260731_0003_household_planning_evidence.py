"""Add roles, invitations, household plans, reservations, and evidence catalogs.

Revision ID: 20260731_0003
Revises: 20260731_0002
Create Date: 2026-07-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260731_0003"
down_revision: Union[str, None] = "20260731_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {value["name"] for value in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {value["name"] for value in sa.inspect(op.get_bind()).get_indexes(table)}


def _unique_constraints(table: str) -> set[str]:
    return {
        value["name"]
        for value in sa.inspect(op.get_bind()).get_unique_constraints(table)
        if value.get("name")
    }


def _ensure_index(table: str, name: str, columns: list[str]) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns)


def _add_member_columns() -> None:
    existing = _columns("household_members")
    with op.batch_alter_table("household_members") as batch:
        if "role" not in existing:
            batch.add_column(
                sa.Column("role", sa.String(), nullable=True, server_default="viewer")
            )
        for name in (
            "target_calories",
            "target_protein_g",
            "target_carbs_g",
            "target_fat_g",
        ):
            if name not in existing:
                batch.add_column(sa.Column(name, sa.Integer(), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE household_members SET role = 'owner' "
            "WHERE linked_user_id = (SELECT owner_user_id FROM households "
            "WHERE households.id = household_members.household_id)"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE household_members SET role = 'viewer' "
            "WHERE role IS NULL OR role NOT IN ('viewer','editor','owner')"
        )
    )
    with op.batch_alter_table("household_members") as batch:
        batch.alter_column(
            "role",
            existing_type=sa.String(),
            nullable=False,
            server_default=None,
        )

    duplicates = bind.execute(
        sa.text(
            "SELECT household_id, linked_user_id, COUNT(*) AS count_value "
            "FROM household_members WHERE linked_user_id IS NOT NULL "
            "GROUP BY household_id, linked_user_id HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        raise RuntimeError(
            "Duplicate linked household members must be resolved before migration: "
            + ", ".join(f"{row[0]}:{row[1]}({row[2]})" for row in duplicates)
        )
    if "uq_household_linked_user" not in _unique_constraints("household_members"):
        with op.batch_alter_table("household_members") as batch:
            batch.create_unique_constraint(
                "uq_household_linked_user",
                ["household_id", "linked_user_id"],
            )
    _ensure_index("household_members", "ix_household_members_role", ["role"])


def upgrade() -> None:
    tables = _tables()
    if "storage_policies" not in tables:
        op.create_table(
            "storage_policies",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("policy_key", sa.String(), nullable=False),
            sa.Column("food_category", sa.String(), nullable=False),
            sa.Column("storage_state", sa.String(), nullable=False),
            sa.Column("duration_min_hours", sa.Float(), nullable=True),
            sa.Column("duration_max_hours", sa.Float(), nullable=True),
            sa.Column("maximum_temperature_c", sa.Float(), nullable=True),
            sa.Column("source_name", sa.String(), nullable=False),
            sa.Column("source_url", sa.String(), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "safety_scope",
                sa.String(),
                nullable=False,
                server_default="general_guidance",
            ),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.CheckConstraint(
                "duration_max_hours IS NULL OR duration_min_hours IS NULL OR "
                "duration_max_hours >= duration_min_hours",
                name="ck_storage_policy_valid_duration",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("policy_key", name="uq_storage_policy_key"),
        )
    for name, columns in (
        ("ix_storage_policies_policy_key", ["policy_key"]),
        ("ix_storage_policies_food_category", ["food_category"]),
        ("ix_storage_policies_storage_state", ["storage_state"]),
    ):
        _ensure_index("storage_policies", name, columns)

    if "household_members" in _tables():
        _add_member_columns()

    if "meal_plans" in _tables() and "household_id" not in _columns("meal_plans"):
        with op.batch_alter_table("meal_plans") as batch:
            batch.add_column(sa.Column("household_id", sa.String(), nullable=True))
            batch.create_foreign_key(
                "fk_meal_plans_household_id",
                "households",
                ["household_id"],
                ["id"],
                ondelete="SET NULL",
            )
    _ensure_index("meal_plans", "ix_meal_plans_household_id", ["household_id"])

    if "leftover_batches" in _tables() and "storage_policy_key" not in _columns(
        "leftover_batches"
    ):
        with op.batch_alter_table("leftover_batches") as batch:
            batch.add_column(
                sa.Column("storage_policy_key", sa.String(), nullable=True)
            )
            batch.create_foreign_key(
                "fk_leftovers_storage_policy_key",
                "storage_policies",
                ["storage_policy_key"],
                ["policy_key"],
                ondelete="SET NULL",
            )
    _ensure_index(
        "leftover_batches",
        "ix_leftover_batches_storage_policy_key",
        ["storage_policy_key"],
    )

    if "household_invitations" not in _tables():
        op.create_table(
            "household_invitations",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("household_id", sa.String(), nullable=False),
            sa.Column("invited_email", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_user_id", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["household_id"], ["households.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "token_hash", name="uq_household_invitation_token_hash"
            ),
        )
    for name, columns in (
        ("ix_household_invitations_household_id", ["household_id"]),
        ("ix_household_invitations_invited_email", ["invited_email"]),
        ("ix_household_invitations_token_hash", ["token_hash"]),
        ("ix_household_invitations_expires_at", ["expires_at"]),
    ):
        _ensure_index("household_invitations", name, columns)

    if "stock_reservations" not in _tables():
        op.create_table(
            "stock_reservations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("household_id", sa.String(), nullable=False),
            sa.Column("pantry_item_id", sa.Integer(), nullable=True),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("canonical_name", sa.String(), nullable=False),
            sa.Column("quantity_min", sa.Float(), nullable=False),
            sa.Column("quantity_max", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(), nullable=False),
            sa.Column(
                "status", sa.String(), nullable=False, server_default="active"
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
            sa.CheckConstraint(
                "quantity_min >= 0", name="ck_reservation_min_nonnegative"
            ),
            sa.CheckConstraint(
                "quantity_max >= quantity_min",
                name="ck_reservation_valid_range",
            ),
            sa.ForeignKeyConstraint(
                ["household_id"], ["households.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["pantry_item_id"], ["pantry_items.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["plan_id"], ["meal_plans.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "plan_id", "pantry_item_id", name="uq_plan_pantry_reservation"
            ),
        )
    for name, columns in (
        ("ix_stock_reservations_household_id", ["household_id"]),
        ("ix_stock_reservations_pantry_item_id", ["pantry_item_id"]),
        ("ix_stock_reservations_plan_id", ["plan_id"]),
        ("ix_stock_reservations_canonical_name", ["canonical_name"]),
        ("ix_stock_reservations_status", ["status"]),
        ("ix_stock_reservations_expires_at", ["expires_at"]),
    ):
        _ensure_index("stock_reservations", name, columns)

    if "ingredient_conversions" not in _tables():
        op.create_table(
            "ingredient_conversions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("canonical_name", sa.String(), nullable=False),
            sa.Column("from_unit", sa.String(), nullable=False),
            sa.Column("to_unit", sa.String(), nullable=False),
            sa.Column("multiplier_min", sa.Float(), nullable=False),
            sa.Column("multiplier_max", sa.Float(), nullable=False),
            sa.Column("source_name", sa.String(), nullable=False),
            sa.Column("source_url", sa.String(), nullable=False),
            sa.Column("source_version", sa.String(), nullable=False),
            sa.Column(
                "evidence_status",
                sa.String(),
                nullable=False,
                server_default="external_unverified",
            ),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.CheckConstraint(
                "multiplier_min > 0", name="ck_conversion_min_positive"
            ),
            sa.CheckConstraint(
                "multiplier_max >= multiplier_min",
                name="ck_conversion_valid_range",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "canonical_name",
                "from_unit",
                "to_unit",
                "source_name",
                "source_version",
                name="uq_conversion_evidence",
            ),
        )
    _ensure_index(
        "ingredient_conversions",
        "ix_ingredient_conversions_canonical_name",
        ["canonical_name"],
    )


def downgrade() -> None:
    tables = _tables()
    for table in (
        "ingredient_conversions",
        "stock_reservations",
        "household_invitations",
    ):
        if table in tables:
            op.drop_table(table)
            tables.remove(table)

    if "leftover_batches" in tables and "storage_policy_key" in _columns(
        "leftover_batches"
    ):
        with op.batch_alter_table("leftover_batches") as batch:
            batch.drop_column("storage_policy_key")
    if "meal_plans" in tables and "household_id" in _columns("meal_plans"):
        with op.batch_alter_table("meal_plans") as batch:
            batch.drop_column("household_id")
    if "household_members" in tables:
        with op.batch_alter_table("household_members") as batch:
            if "uq_household_linked_user" in _unique_constraints(
                "household_members"
            ):
                batch.drop_constraint(
                    "uq_household_linked_user", type_="unique"
                )
            for name in (
                "target_fat_g",
                "target_carbs_g",
                "target_protein_g",
                "target_calories",
                "role",
            ):
                if name in _columns("household_members"):
                    batch.drop_column(name)
    if "storage_policies" in tables:
        op.drop_table("storage_policies")
