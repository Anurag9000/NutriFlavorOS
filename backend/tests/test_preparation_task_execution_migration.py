from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[2]
REVISION = "20260802_0014"
PREVIOUS_REVISION = "20260802_0013"
TABLE = "preparation_task_execution_events"
EXPECTED_INDEXES = {
    "ix_preparation_task_events_schedule_created",
    "ix_preparation_task_events_schedule_task_created",
    "ix_preparation_task_events_household_created",
}
EXPECTED_COLUMNS = {
    "id",
    "schedule_id",
    "household_id",
    "task_id",
    "event_type",
    "actor_user_id",
    "from_state",
    "to_state",
    "planned_start_minute",
    "planned_finish_minute",
    "actual_minute",
    "deviation_minutes",
    "reason",
    "notes",
    "event_metadata",
    "idempotency_key",
    "request_fingerprint",
    "schedule_version_before",
    "schedule_version_after",
    "created_at",
}


def config(url: str) -> Config:
    value = Config(str(ROOT / "alembic.ini"))
    value.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    value.set_main_option("sqlalchemy.url", url)
    return value


def test_task_execution_migration_upgrades_and_downgrades(tmp_path):
    url = f"sqlite:///{tmp_path / 'task-execution-migration.db'}"
    cfg = config(url)
    engine = create_engine(url)

    command.upgrade(cfg, PREVIOUS_REVISION)
    assert TABLE not in inspect(engine).get_table_names()

    command.upgrade(cfg, REVISION)
    inspector = inspect(engine)
    assert TABLE in inspector.get_table_names()
    assert {value["name"] for value in inspector.get_columns(TABLE)} == EXPECTED_COLUMNS
    assert {value["name"] for value in inspector.get_indexes(TABLE)} == EXPECTED_INDEXES
    unique_names = {value["name"] for value in inspector.get_unique_constraints(TABLE)}
    assert "uq_preparation_task_event_schedule_idempotency" in unique_names
    check_names = {value["name"] for value in inspector.get_check_constraints(TABLE)}
    assert {
        "ck_preparation_task_event_task_nonblank",
        "ck_preparation_task_event_type",
        "ck_preparation_task_event_transition",
        "ck_preparation_task_event_deviation",
        "ck_preparation_task_event_reason_required",
        "ck_preparation_task_event_schedule_versions",
    }.issubset(check_names)

    command.downgrade(cfg, PREVIOUS_REVISION)
    assert TABLE not in inspect(engine).get_table_names()
