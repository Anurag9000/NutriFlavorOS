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


def _checks(inspector, table: str) -> set[str]:
    return {
        value["name"]
        for value in inspector.get_check_constraints(table)
    }


def test_preparation_state_constraints_upgrade_and_downgrade(tmp_path):
    database = tmp_path / "preparation-state-constraints.db"
    url = f"sqlite:///{database}"
    config = _config(url)
    engine = create_engine(url)

    command.upgrade(config, "20260801_0010")
    before = inspect(engine)
    assert "ck_resource_calendar_review_state" not in _checks(
        before, "resource_calendar_versions"
    )
    assert "ck_persisted_schedule_approval_state" not in _checks(
        before, "persisted_preparation_schedules"
    )
    assert "ck_preparation_schedule_event_transition_pair" not in _checks(
        before, "preparation_schedule_events"
    )

    command.upgrade(config, "20260801_0011")
    current = inspect(engine)
    assert {
        "ck_resource_calendar_review_state",
        "ck_resource_calendar_active_reviewed",
    } <= _checks(current, "resource_calendar_versions")
    assert {
        "ck_persisted_schedule_approval_state",
        "ck_persisted_schedule_invalidation_state",
    } <= _checks(current, "persisted_preparation_schedules")
    assert {
        "ck_preparation_schedule_event_transition_pair",
        "ck_preparation_schedule_event_reason_nonblank",
    } <= _checks(current, "preparation_schedule_events")

    command.downgrade(config, "20260801_0010")
    after = inspect(engine)
    assert "ck_resource_calendar_review_state" not in _checks(
        after, "resource_calendar_versions"
    )
    assert "ck_persisted_schedule_approval_state" not in _checks(
        after, "persisted_preparation_schedules"
    )
    assert "ck_preparation_schedule_event_transition_pair" not in _checks(
        after, "preparation_schedule_events"
    )
