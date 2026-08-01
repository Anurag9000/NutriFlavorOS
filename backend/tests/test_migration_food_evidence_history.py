from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def _load_migration(operations: Operations):
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260801_0007_version_food_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0007", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def test_revision_backfills_legacy_evidence_conservatively(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-evidence.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE ingredient_conversions ("
                "id INTEGER PRIMARY KEY, canonical_name VARCHAR NOT NULL, "
                "from_unit VARCHAR NOT NULL, to_unit VARCHAR NOT NULL, "
                "multiplier_min FLOAT NOT NULL, multiplier_max FLOAT NOT NULL, "
                "source_name VARCHAR NOT NULL, source_url VARCHAR NOT NULL, "
                "source_version VARCHAR NOT NULL, evidence_status VARCHAR NOT NULL, "
                "reviewed_at DATETIME, notes VARCHAR, active BOOLEAN NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE storage_policies ("
                "id INTEGER PRIMARY KEY, policy_key VARCHAR NOT NULL, "
                "food_category VARCHAR NOT NULL, storage_state VARCHAR NOT NULL, "
                "duration_min_hours FLOAT, duration_max_hours FLOAT, "
                "maximum_temperature_c FLOAT, source_name VARCHAR NOT NULL, "
                "source_url VARCHAR NOT NULL, reviewed_at DATETIME, "
                "safety_scope VARCHAR NOT NULL, notes VARCHAR, active BOOLEAN NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE leftover_batches ("
                "id INTEGER PRIMARY KEY, storage_policy_key VARCHAR)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO ingredient_conversions VALUES "
                "(1,'rice','cup','g',120,120,'Source A','https://a.test','1',"
                "'reviewed','2026-01-01T00:00:00+00:00','unique',1),"
                "(2,'flour','cup','g',125,125,'Source B','https://b.test','1',"
                "'reviewed','2026-01-01T00:00:00+00:00','duplicate one',1),"
                "(3,'flour','cup','g',130,130,'Source C','https://c.test','1',"
                "'reviewed','2026-01-02T00:00:00+00:00','duplicate two',1),"
                "(4,'oil','tbsp','g',14,14,'Source D','https://d.test','1',"
                "'external_unverified',NULL,'unreviewed',1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO storage_policies VALUES "
                "(1,'pizza_refrigerated','pizza','refrigerated',72,96,4,"
                "'Official','https://policy.test','2026-01-01T00:00:00+00:00',"
                "'general_home_storage','reviewed',1),"
                "(2,'unknown_policy','unknown','refrigerated',NULL,NULL,NULL,"
                "'Unknown','https://unknown.test',NULL,'unknown','unreviewed',1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO leftover_batches VALUES "
                "(10,'pizza_refrigerated'),(11,'unknown_policy')"
            )
        )
        context = MigrationContext.configure(connection)
        module = _load_migration(Operations(context))
        module.upgrade()

    inspector = inspect(engine)
    assert {
        "ingredient_conversion_versions",
        "storage_policy_versions",
        "leftover_storage_policy_evidence",
    }.issubset(inspector.get_table_names())
    conversion_indexes = {
        value["name"]
        for value in inspector.get_indexes("ingredient_conversion_versions")
    }
    storage_indexes = {
        value["name"]
        for value in inspector.get_indexes("storage_policy_versions")
    }
    assert "uq_active_reviewed_conversion_key" in conversion_indexes
    assert "uq_active_reviewed_storage_policy_key" in storage_indexes

    with engine.connect() as connection:
        conversions = connection.execute(
            text(
                "SELECT canonical_name, evidence_status, active, content_hash "
                "FROM ingredient_conversion_versions ORDER BY id"
            )
        ).mappings().all()
        assert len(conversions) == 4
        rice = next(value for value in conversions if value["canonical_name"] == "rice")
        assert rice["evidence_status"] == "reviewed"
        assert bool(rice["active"]) is True
        flour = [value for value in conversions if value["canonical_name"] == "flour"]
        assert len(flour) == 2
        assert all(bool(value["active"]) is False for value in flour)
        assert all(len(value["content_hash"]) == 64 for value in conversions)

        policies = connection.execute(
            text(
                "SELECT id, policy_key, evidence_status, active, content_hash "
                "FROM storage_policy_versions ORDER BY id"
            )
        ).mappings().all()
        pizza = next(value for value in policies if value["policy_key"] == "pizza_refrigerated")
        unknown = next(value for value in policies if value["policy_key"] == "unknown_policy")
        assert pizza["evidence_status"] == "reviewed"
        assert bool(pizza["active"]) is True
        assert unknown["evidence_status"] == "legacy_unreviewed"
        assert bool(unknown["active"]) is False
        assert len(pizza["content_hash"]) == 64

        links = connection.execute(
            text(
                "SELECT leftover_id, storage_policy_version_id "
                "FROM leftover_storage_policy_evidence ORDER BY leftover_id"
            )
        ).mappings().all()
        assert links == [
            {
                "leftover_id": 10,
                "storage_policy_version_id": pizza["id"],
            }
        ]
