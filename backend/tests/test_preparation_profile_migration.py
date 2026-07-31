from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, inspect, select


ROOT = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_preparation_profile_migration_creates_constraints_and_indexes(
    tmp_path,
    monkeypatch,
):
    database = tmp_path / "preparation-profile.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(_config(url), "head")

    inspector = inspect(create_engine(url))
    table = "recipe_preparation_profiles"
    assert table in inspector.get_table_names()
    columns = {value["name"] for value in inspector.get_columns(table)}
    assert {
        "recipe_id",
        "profile_version",
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
        "content_hash",
        "supersedes_profile_id",
        "active",
    } <= columns
    checks = {
        value["name"]
        for value in inspector.get_check_constraints(table)
        if value.get("name")
    }
    assert {
        "ck_recipe_preparation_profile_status",
        "ck_recipe_preparation_profile_schema_version",
        "ck_recipe_preparation_profile_version_nonempty",
        "ck_recipe_preparation_profile_servings_min",
        "ck_recipe_preparation_profile_servings_range",
    } <= checks
    uniques = {
        value["name"]
        for value in inspector.get_unique_constraints(table)
        if value.get("name")
    }
    assert "uq_recipe_preparation_profile_version" in uniques
    indexes = {
        value["name"] for value in inspector.get_indexes(table) if value.get("name")
    }
    assert {
        "ix_recipe_preparation_profiles_content_hash",
        "ix_recipe_preparation_profiles_supersedes_profile_id",
        "uq_active_reviewed_preparation_profile_recipe",
    } <= indexes


def test_versioning_migration_backfills_existing_profile_hash(tmp_path, monkeypatch):
    database = tmp_path / "preparation-profile-backfill.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config(url)
    command.upgrade(config, "20260731_0005")

    engine = create_engine(url)
    metadata = MetaData()
    recipes = Table("recipes", metadata, autoload_with=engine)
    profiles = Table("recipe_preparation_profiles", metadata, autoload_with=engine)
    now = datetime(2026, 7, 31, tzinfo=timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            recipes.insert().values(
                id="migration-soup",
                name="Migration soup",
                description="",
                ingredients=["water"],
                ingredient_data=[],
                servings=2,
                calories=100,
                macros={},
                flavor_profile={},
                tags=[],
                instructions=[],
                estimated_cost=1,
                nutrition_basis="per_serving",
            )
        )
        connection.execute(
            profiles.insert().values(
                recipe_id="migration-soup",
                schema_version="1",
                supported_servings_min=1,
                supported_servings_max=4,
                task_templates=[
                    {
                        "template_id": "heat",
                        "name": "Heat",
                        "duration_min_minutes": 5,
                        "duration_max_minutes": 10,
                        "resource_demands": {"burner": 1},
                        "dependencies": [],
                        "active_work": True,
                        "unattended_allowed": False,
                        "notes": None,
                    }
                ],
                source_name="Migration fixture",
                source_url="https://example.test/migration-soup",
                source_version="1",
                evidence_status="reviewed",
                reviewed_at=now,
                reviewed_by="Migration reviewer",
                notes=None,
                active=True,
                created_at=now,
                updated_at=now,
            )
        )

    command.upgrade(config, "head")
    metadata = MetaData()
    profiles = Table("recipe_preparation_profiles", metadata, autoload_with=engine)
    with engine.connect() as connection:
        row = connection.execute(select(profiles)).mappings().one()
    assert row["profile_version"] == "1"
    assert len(row["content_hash"]) == 64
    int(row["content_hash"], 16)
