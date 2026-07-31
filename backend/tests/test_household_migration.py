from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,inspect
ROOT=Path(__file__).resolve().parents[2]
def test_household_research_migration_creates_runtime_tables(tmp_path,monkeypatch):
    database=tmp_path/"household.db"; url=f"sqlite:///{database}"; monkeypatch.setenv("DATABASE_URL",url); config=Config(str(ROOT/"alembic.ini")); config.set_main_option("script_location",str(ROOT/"backend"/"migrations")); config.set_main_option("sqlalchemy.url",url); command.upgrade(config,"head")
    inspector=inspect(create_engine(url)); assert {"households","household_members","pantry_items","leftover_batches","inventory_events","experiment_runs"}.issubset(set(inspector.get_table_names())); pantry={column["name"] for column in inspector.get_columns("pantry_items")}; indexes={index["name"] for index in inspector.get_indexes("inventory_events")}; assert {"quantity_min","quantity_max","unit","version","expires_at"}.issubset(pantry); assert "ix_inventory_events_household_id" in indexes
