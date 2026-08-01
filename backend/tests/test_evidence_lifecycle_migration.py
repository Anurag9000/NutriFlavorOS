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


def test_lifecycle_migration_adds_exact_target_ledger_and_downgrades(tmp_path):
    database = tmp_path / "lifecycle-migration.db"
    url = f"sqlite:///{database}"
    config = _config(url)

    command.upgrade(config, "20260801_0007")
    engine = create_engine(url)
    before = inspect(engine)
    assert "evidence_lifecycle_events" not in before.get_table_names()

    command.upgrade(config, "20260801_0008")
    current = inspect(engine)
    assert "evidence_lifecycle_events" in current.get_table_names()
    columns = {value["name"]: value for value in current.get_columns("evidence_lifecycle_events")}
    assert set(columns) == {
        "id",
        "evidence_kind",
        "conversion_version_id",
        "storage_policy_version_id",
        "action",
        "actor",
        "reason",
        "event_metadata",
        "idempotency_key",
        "request_fingerprint",
        "target_was_active",
        "created_at",
    }
    assert columns["evidence_kind"]["nullable"] is False
    assert columns["idempotency_key"]["nullable"] is False
    assert columns["request_fingerprint"]["nullable"] is False

    checks = {
        value["name"]: value["sqltext"]
        for value in current.get_check_constraints("evidence_lifecycle_events")
    }
    assert "ck_evidence_lifecycle_kind" in checks
    assert "ck_evidence_lifecycle_action" in checks
    assert "ck_evidence_lifecycle_exactly_one_target" in checks
    assert "ck_evidence_lifecycle_fingerprint_length" in checks

    unique_names = {
        value["name"]
        for value in current.get_unique_constraints("evidence_lifecycle_events")
    }
    assert "uq_evidence_lifecycle_idempotency_key" in unique_names

    foreign_keys = {
        value["name"]: tuple(value["referred_columns"])
        for value in current.get_foreign_keys("evidence_lifecycle_events")
    }
    assert foreign_keys == {
        "fk_evidence_lifecycle_conversion": ("id",),
        "fk_evidence_lifecycle_policy": ("id",),
    }

    indexes = {value["name"] for value in current.get_indexes("evidence_lifecycle_events")}
    assert {
        "ix_evidence_lifecycle_events_evidence_kind",
        "ix_evidence_lifecycle_events_action",
        "ix_evidence_lifecycle_events_request_fingerprint",
        "ix_evidence_lifecycle_conversion_created",
        "ix_evidence_lifecycle_policy_created",
    } <= indexes

    command.downgrade(config, "20260801_0007")
    after = inspect(engine)
    assert "evidence_lifecycle_events" not in after.get_table_names()
