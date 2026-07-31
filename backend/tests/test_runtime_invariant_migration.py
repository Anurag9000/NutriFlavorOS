from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


ROOT = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_fresh_head_contains_named_runtime_invariant_constraints(tmp_path, monkeypatch):
    database = tmp_path / "runtime-invariants.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(_config(url), "head")

    inspector = inspect(create_engine(url))
    expected = {
        "households": {"ck_household_version_positive"},
        "household_members": {
            "ck_member_valid_role",
            "ck_member_target_calories",
            "ck_member_target_protein",
            "ck_member_target_carbs",
            "ck_member_target_fat",
        },
        "household_invitations": {
            "ck_invitation_valid_role",
            "ck_invitation_single_terminal_state",
        },
        "pantry_items": {"ck_pantry_version_positive"},
        "leftover_batches": {"ck_leftover_version_positive"},
        "inventory_events": {"ck_inventory_event_valid_type"},
        "stock_reservations": {
            "ck_reservation_valid_status",
            "ck_reservation_version_positive",
        },
        "storage_policies": {
            "ck_storage_policy_min_nonnegative",
            "ck_storage_policy_max_nonnegative",
        },
    }
    for table, names in expected.items():
        observed = {
            constraint["name"]
            for constraint in inspector.get_check_constraints(table)
            if constraint.get("name")
        }
        assert names <= observed


def test_fresh_schema_rejects_invalid_household_role_and_version(tmp_path, monkeypatch):
    database = tmp_path / "invalid-runtime-row.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(_config(url), "head")
    engine = create_engine(url)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, name, liked_ingredients, disliked_ingredients, "
                "allergies, dietary_restrictions, health_conditions, medications) "
                "VALUES ('owner@example.test', 'Owner', '[]', '[]', '[]', '[]', '[]', '[]')"
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO households "
                    "(id, owner_user_id, name, timezone, version, created_at, updated_at) "
                    "VALUES ('bad-home', 'owner@example.test', 'Bad', 'UTC', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO households "
                "(id, owner_user_id, name, timezone, version, created_at, updated_at) "
                "VALUES ('home', 'owner@example.test', 'Home', 'UTC', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO household_members "
                    "(household_id, display_name, linked_user_id, role, servings_multiplier, "
                    "allergies, dietary_restrictions, disliked_ingredients, active, created_at) "
                    "VALUES ('home', 'Invalid', NULL, 'administrator', 1, '[]', '[]', '[]', 1, CURRENT_TIMESTAMP)"
                )
            )


def test_existing_invalid_0003_data_blocks_invariant_upgrade(tmp_path, monkeypatch):
    database = tmp_path / "blocked-runtime-upgrade.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config(url)
    command.upgrade(config, "20260731_0003")
    engine = create_engine(url)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, name, liked_ingredients, disliked_ingredients, "
                "allergies, dietary_restrictions, health_conditions, medications) "
                "VALUES ('owner@example.test', 'Owner', '[]', '[]', '[]', '[]', '[]', '[]')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO households "
                "(id, owner_user_id, name, timezone, version, created_at, updated_at) "
                "VALUES ('home', 'owner@example.test', 'Home', 'UTC', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO household_members "
                "(household_id, display_name, linked_user_id, role, servings_multiplier, "
                "allergies, dietary_restrictions, disliked_ingredients, target_calories, "
                "active, created_at) "
                "VALUES ('home', 'Invalid', NULL, 'viewer', 1, '[]', '[]', '[]', -5, 1, CURRENT_TIMESTAMP)"
            )
        )

    with pytest.raises(RuntimeError, match="household_members.target_calories=1"):
        command.upgrade(config, "head")
