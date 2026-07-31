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


def test_preparation_profile_migration_creates_constraints_and_indexes(tmp_path, monkeypatch):
    database = tmp_path / "preparation-profile.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(_config(url), "head")

    inspector = inspect(create_engine(url))
    assert "recipe_preparation_profiles" in inspector.get_table_names()
    columns = {
        value["name"] for value in inspector.get_columns("recipe_preparation_profiles")
    }
    assert {
        "recipe_id",
        "schema_version",
        "supported_servings_min",
        "supported_servings_max",
        "task_templates",
        "source_name",
        "source_url",
        "source_version",
        "evidence_status",
        "reviewed_at",
        "reviewed_by",
        "active",
    } <= columns
    checks = {
        value["name"]
        for value in inspector.get_check_constraints("recipe_preparation_profiles")
        if value.get("name")
    }
    assert {
        "ck_recipe_preparation_profile_status",
        "ck_recipe_preparation_profile_schema_version",
        "ck_recipe_preparation_profile_servings_min",
        "ck_recipe_preparation_profile_servings_range",
    } <= checks
    uniques = {
        value["name"]
        for value in inspector.get_unique_constraints("recipe_preparation_profiles")
        if value.get("name")
    }
    assert "uq_recipe_preparation_profile_recipe" in uniques
