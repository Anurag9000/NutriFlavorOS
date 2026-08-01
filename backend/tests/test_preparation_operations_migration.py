from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _foreign_keys(inspector, table: str) -> dict[tuple[str, ...], dict]:
    return {
        tuple(value["constrained_columns"]): {
            "referred_table": value["referred_table"],
            "referred_columns": tuple(value["referred_columns"]),
            "ondelete": str((value.get("options") or {}).get("ondelete") or "").upper(),
        }
        for value in inspector.get_foreign_keys(table)
    }


def test_preparation_operations_migration_creates_and_drops_complete_schema(tmp_path):
    database = tmp_path / "preparation-operations.db"
    url = f"sqlite:///{database}"
    config = _config(url)
    engine = create_engine(url)

    command.upgrade(config, "20260801_0008")
    before = inspect(engine)
    for table in (
        "resource_calendar_versions",
        "household_preparation_resources",
        "persisted_preparation_schedules",
        "preparation_schedule_events",
    ):
        assert table not in before.get_table_names()

    command.upgrade(config, "20260801_0009")
    current = inspect(engine)
    assert {
        "resource_calendar_versions",
        "household_preparation_resources",
        "persisted_preparation_schedules",
        "preparation_schedule_events",
    } <= set(current.get_table_names())

    calendar_checks = {
        value["name"] for value in current.get_check_constraints("resource_calendar_versions")
    }
    assert {
        "ck_resource_calendar_evidence_status",
        "ck_resource_calendar_horizon",
        "ck_resource_calendar_hash_length",
        "ck_resource_calendar_request_fingerprint_length",
    } <= calendar_checks
    calendar_uniques = {
        value["name"] for value in current.get_unique_constraints("resource_calendar_versions")
    }
    assert {
        "uq_resource_calendar_household_version",
        "uq_resource_calendar_household_idempotency",
    } <= calendar_uniques
    calendar_indexes = {
        value["name"]: value
        for value in current.get_indexes("resource_calendar_versions")
    }
    assert calendar_indexes[
        "uq_active_reviewed_resource_calendar_household"
    ]["unique"] is True

    assert _foreign_keys(current, "resource_calendar_versions") == {
        ("household_id",): {
            "referred_table": "households",
            "referred_columns": ("id",),
            "ondelete": "CASCADE",
        },
        ("supersedes_calendar_id",): {
            "referred_table": "resource_calendar_versions",
            "referred_columns": ("id",),
            "ondelete": "SET NULL",
        },
        ("created_by_user_id",): {
            "referred_table": "users",
            "referred_columns": ("id",),
            "ondelete": "RESTRICT",
        },
    }

    resource_uniques = {
        value["name"]
        for value in current.get_unique_constraints("household_preparation_resources")
    }
    assert "uq_household_preparation_resource_calendar_key" in resource_uniques
    assert _foreign_keys(current, "household_preparation_resources") == {
        ("calendar_version_id",): {
            "referred_table": "resource_calendar_versions",
            "referred_columns": ("id",),
            "ondelete": "CASCADE",
        }
    }

    schedule_checks = {
        value["name"]
        for value in current.get_check_constraints("persisted_preparation_schedules")
    }
    assert {
        "ck_persisted_schedule_status",
        "ck_persisted_schedule_version_positive",
        "ck_persisted_schedule_calendar_hash_length",
        "ck_persisted_schedule_occurrence_hash_length",
        "ck_persisted_schedule_hash_length",
        "ck_persisted_schedule_creation_fingerprint_length",
        "ck_persisted_schedule_plan_source_pair",
    } <= schedule_checks
    assert _foreign_keys(current, "persisted_preparation_schedules") == {
        ("household_id",): {
            "referred_table": "households",
            "referred_columns": ("id",),
            "ondelete": "CASCADE",
        },
        ("calendar_version_id",): {
            "referred_table": "resource_calendar_versions",
            "referred_columns": ("id",),
            "ondelete": "RESTRICT",
        },
        ("source_plan_id",): {
            "referred_table": "meal_plans",
            "referred_columns": ("id",),
            "ondelete": "RESTRICT",
        },
        ("created_by_user_id",): {
            "referred_table": "users",
            "referred_columns": ("id",),
            "ondelete": "RESTRICT",
        },
        ("approved_by_user_id",): {
            "referred_table": "users",
            "referred_columns": ("id",),
            "ondelete": "RESTRICT",
        },
    }

    event_checks = {
        value["name"] for value in current.get_check_constraints("preparation_schedule_events")
    }
    assert {
        "ck_preparation_schedule_event_type",
        "ck_preparation_schedule_event_to_status",
        "ck_preparation_schedule_event_from_status",
        "ck_preparation_schedule_event_fingerprint_length",
    } <= event_checks
    event_uniques = {
        value["name"]
        for value in current.get_unique_constraints("preparation_schedule_events")
    }
    assert "uq_preparation_schedule_event_household_idempotency" in event_uniques
    assert _foreign_keys(current, "preparation_schedule_events") == {
        ("schedule_id",): {
            "referred_table": "persisted_preparation_schedules",
            "referred_columns": ("id",),
            "ondelete": "CASCADE",
        },
        ("household_id",): {
            "referred_table": "households",
            "referred_columns": ("id",),
            "ondelete": "CASCADE",
        },
        ("actor_user_id",): {
            "referred_table": "users",
            "referred_columns": ("id",),
            "ondelete": "RESTRICT",
        },
    }

    command.downgrade(config, "20260801_0008")
    after = inspect(engine)
    for table in (
        "resource_calendar_versions",
        "household_preparation_resources",
        "persisted_preparation_schedules",
        "preparation_schedule_events",
    ):
        assert table not in after.get_table_names()
