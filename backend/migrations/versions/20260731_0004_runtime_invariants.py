"""Enforce stable household, inventory, and reservation invariants.

Revision ID: 20260731_0004
Revises: 20260731_0003
Create Date: 2026-07-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260731_0004"
down_revision: Union[str, None] = "20260731_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CHECKS: dict[str, tuple[tuple[str, str], ...]] = {
    "households": (
        ("ck_household_version_positive", "version >= 1"),
    ),
    "household_members": (
        ("ck_member_valid_role", "role IN ('viewer','editor','owner')"),
        (
            "ck_member_target_calories",
            "target_calories IS NULL OR (target_calories > 0 AND target_calories <= 20000)",
        ),
        (
            "ck_member_target_protein",
            "target_protein_g IS NULL OR (target_protein_g >= 0 AND target_protein_g <= 2000)",
        ),
        (
            "ck_member_target_carbs",
            "target_carbs_g IS NULL OR (target_carbs_g >= 0 AND target_carbs_g <= 4000)",
        ),
        (
            "ck_member_target_fat",
            "target_fat_g IS NULL OR (target_fat_g >= 0 AND target_fat_g <= 2000)",
        ),
    ),
    "household_invitations": (
        ("ck_invitation_valid_role", "role IN ('viewer','editor')"),
        (
            "ck_invitation_single_terminal_state",
            "accepted_at IS NULL OR revoked_at IS NULL",
        ),
    ),
    "pantry_items": (
        ("ck_pantry_version_positive", "version >= 1"),
    ),
    "leftover_batches": (
        ("ck_leftover_version_positive", "version >= 1"),
    ),
    "inventory_events": (
        (
            "ck_inventory_event_valid_type",
            "event_type IN ('purchase','consume','adjust','discard','leftover_create','leftover_consume','reservation_commit')",
        ),
    ),
    "stock_reservations": (
        (
            "ck_reservation_valid_status",
            "status IN ('active','released','consumed','expired')",
        ),
        ("ck_reservation_version_positive", "version >= 1"),
    ),
    "storage_policies": (
        (
            "ck_storage_policy_min_nonnegative",
            "duration_min_hours IS NULL OR duration_min_hours >= 0",
        ),
        (
            "ck_storage_policy_max_nonnegative",
            "duration_max_hours IS NULL OR duration_max_hours >= 0",
        ),
    ),
}


PREFLIGHTS: tuple[tuple[str, str], ...] = (
    ("households.version", "SELECT COUNT(*) FROM households WHERE version < 1"),
    (
        "household_members.role",
        "SELECT COUNT(*) FROM household_members WHERE role NOT IN ('viewer','editor','owner')",
    ),
    (
        "household_members.target_calories",
        "SELECT COUNT(*) FROM household_members WHERE target_calories IS NOT NULL AND (target_calories <= 0 OR target_calories > 20000)",
    ),
    (
        "household_members.target_protein_g",
        "SELECT COUNT(*) FROM household_members WHERE target_protein_g IS NOT NULL AND (target_protein_g < 0 OR target_protein_g > 2000)",
    ),
    (
        "household_members.target_carbs_g",
        "SELECT COUNT(*) FROM household_members WHERE target_carbs_g IS NOT NULL AND (target_carbs_g < 0 OR target_carbs_g > 4000)",
    ),
    (
        "household_members.target_fat_g",
        "SELECT COUNT(*) FROM household_members WHERE target_fat_g IS NOT NULL AND (target_fat_g < 0 OR target_fat_g > 2000)",
    ),
    (
        "household_invitations.role",
        "SELECT COUNT(*) FROM household_invitations WHERE role NOT IN ('viewer','editor')",
    ),
    (
        "household_invitations.terminal_state",
        "SELECT COUNT(*) FROM household_invitations WHERE accepted_at IS NOT NULL AND revoked_at IS NOT NULL",
    ),
    ("pantry_items.version", "SELECT COUNT(*) FROM pantry_items WHERE version < 1"),
    (
        "leftover_batches.version",
        "SELECT COUNT(*) FROM leftover_batches WHERE version < 1",
    ),
    (
        "inventory_events.event_type",
        "SELECT COUNT(*) FROM inventory_events WHERE event_type NOT IN ('purchase','consume','adjust','discard','leftover_create','leftover_consume','reservation_commit')",
    ),
    (
        "stock_reservations.status",
        "SELECT COUNT(*) FROM stock_reservations WHERE status NOT IN ('active','released','consumed','expired')",
    ),
    (
        "stock_reservations.version",
        "SELECT COUNT(*) FROM stock_reservations WHERE version < 1",
    ),
    (
        "storage_policies.duration_min_hours",
        "SELECT COUNT(*) FROM storage_policies WHERE duration_min_hours IS NOT NULL AND duration_min_hours < 0",
    ),
    (
        "storage_policies.duration_max_hours",
        "SELECT COUNT(*) FROM storage_policies WHERE duration_max_hours IS NOT NULL AND duration_max_hours < 0",
    ),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _check_names(table: str) -> set[str]:
    return {
        value["name"]
        for value in sa.inspect(op.get_bind()).get_check_constraints(table)
        if value.get("name")
    }


def _preflight() -> None:
    bind = op.get_bind()
    tables = _tables()
    failures: list[str] = []
    for label, statement in PREFLIGHTS:
        table = label.split(".", 1)[0]
        if table not in tables:
            continue
        count = int(bind.execute(sa.text(statement)).scalar() or 0)
        if count:
            failures.append(f"{label}={count}")
    if failures:
        raise RuntimeError(
            "Runtime invariant migration blocked by invalid existing rows: "
            + ", ".join(failures)
        )


def upgrade() -> None:
    _preflight()
    tables = _tables()
    for table, constraints in CHECKS.items():
        if table not in tables:
            continue
        existing = _check_names(table)
        missing = [(name, condition) for name, condition in constraints if name not in existing]
        if not missing:
            continue
        with op.batch_alter_table(table) as batch:
            for name, condition in missing:
                batch.create_check_constraint(name, condition)


def downgrade() -> None:
    tables = _tables()
    for table, constraints in reversed(tuple(CHECKS.items())):
        if table not in tables:
            continue
        existing = _check_names(table)
        removable = [name for name, _ in constraints if name in existing]
        if not removable:
            continue
        with op.batch_alter_table(table) as batch:
            for name in removable:
                batch.drop_constraint(name, type_="check")
