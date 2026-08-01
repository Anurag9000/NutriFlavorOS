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


def _source_plan_fk(inspector) -> dict:
    values = [
        value
        for value in inspector.get_foreign_keys("persisted_preparation_schedules")
        if tuple(value["constrained_columns"]) == ("source_plan_id",)
    ]
    assert len(values) == 1
    value = values[0]
    return {
        "referred_table": value["referred_table"],
        "referred_columns": tuple(value["referred_columns"]),
        "ondelete": str((value.get("options") or {}).get("ondelete") or "").upper(),
    }


def test_schedule_replay_provenance_upgrade_and_downgrade(tmp_path):
    database = tmp_path / "schedule-replay-provenance.db"
    url = f"sqlite:///{database}"
    config = _config(url)
    engine = create_engine(url)

    command.upgrade(config, "20260801_0009")
    before = inspect(engine)
    before_columns = {
        value["name"]
        for value in before.get_columns("persisted_preparation_schedules")
    }
    assert "schedule_request_payload" not in before_columns
    assert "schedule_request_hash" not in before_columns
    assert _source_plan_fk(before) == {
        "referred_table": "meal_plans",
        "referred_columns": ("id",),
        "ondelete": "RESTRICT",
    }

    command.upgrade(config, "20260801_0010")
    current = inspect(engine)
    current_columns = {
        value["name"]: value
        for value in current.get_columns("persisted_preparation_schedules")
    }
    assert current_columns["schedule_request_payload"]["nullable"] is True
    assert current_columns["schedule_request_hash"]["nullable"] is True
    checks = {
        value["name"]
        for value in current.get_check_constraints("persisted_preparation_schedules")
    }
    assert "ck_persisted_schedule_request_provenance_pair" in checks
    indexes = {
        value["name"]
        for value in current.get_indexes("persisted_preparation_schedules")
    }
    assert "ix_persisted_preparation_schedules_schedule_request_hash" in indexes
    assert _source_plan_fk(current) == {
        "referred_table": "meal_plans",
        "referred_columns": ("id",),
        "ondelete": "RESTRICT",
    }

    command.downgrade(config, "20260801_0009")
    after = inspect(engine)
    after_columns = {
        value["name"]
        for value in after.get_columns("persisted_preparation_schedules")
    }
    assert "schedule_request_payload" not in after_columns
    assert "schedule_request_hash" not in after_columns
    assert _source_plan_fk(after) == {
        "referred_table": "meal_plans",
        "referred_columns": ("id",),
        "ondelete": "RESTRICT",
    }
