from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[2]


def _upgrade(database_url: str, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def test_fresh_database_upgrade_creates_versioned_schema(tmp_path, monkeypatch):
    database = tmp_path / "fresh.db"
    url = f"sqlite:///{database}"

    _upgrade(url, monkeypatch)

    inspector = inspect(create_engine(url))
    assert {
        "alembic_version",
        "users",
        "recipes",
        "meal_plans",
        "feedback_events",
    }.issubset(set(inspector.get_table_names()))
    recipe_columns = {column["name"] for column in inspector.get_columns("recipes")}
    plan_columns = {column["name"] for column in inspector.get_columns("meal_plans")}
    assert {
        "ingredient_data",
        "servings",
        "source_name",
        "source_url",
        "source_version",
        "nutrition_basis",
    }.issubset(recipe_columns)
    assert "schema_version" in plan_columns


def test_legacy_database_upgrade_backfills_new_required_fields(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    url = f"sqlite:///{database}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    age INTEGER,
                    weight_kg FLOAT,
                    height_cm FLOAT,
                    gender VARCHAR,
                    activity_level FLOAT,
                    goal VARCHAR,
                    liked_ingredients JSON,
                    disliked_ingredients JSON,
                    dietary_restrictions JSON,
                    health_conditions JSON,
                    created_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE recipes (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    description VARCHAR,
                    image_url VARCHAR,
                    ingredients JSON,
                    calories INTEGER,
                    macros JSON,
                    flavor_profile JSON,
                    tags JSON,
                    cuisine VARCHAR,
                    instructions JSON,
                    estimated_cost FLOAT
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE meal_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id VARCHAR,
                    plan_data JSON,
                    created_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, name, liked_ingredients, disliked_ingredients,
                    dietary_restrictions, health_conditions
                ) VALUES (
                    'legacy@example.com', 'Legacy', '[]', '[]', '[]', '[]'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO recipes (
                    id, name, description, ingredients, calories, macros,
                    flavor_profile, tags, instructions, estimated_cost
                ) VALUES (
                    'r1', 'Legacy recipe', '', '["1 cup rice"]', 300,
                    '{"protein": 6, "carbs": 65, "fat": 1}', '{}', '[]', '[]', 2.0
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO meal_plans (user_id, plan_data)
                VALUES ('legacy@example.com', '{}')
                """
            )
        )

    _upgrade(url, monkeypatch)

    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    recipe_columns = {column["name"] for column in inspector.get_columns("recipes")}
    plan_columns = {column["name"] for column in inspector.get_columns("meal_plans")}
    assert {"hashed_password", "allergies", "medications"}.issubset(user_columns)
    assert {"ingredient_data", "servings", "nutrition_basis"}.issubset(recipe_columns)
    assert "schema_version" in plan_columns
    assert "feedback_events" in inspector.get_table_names()

    with engine.connect() as connection:
        recipe = connection.execute(
            text("SELECT servings, nutrition_basis FROM recipes WHERE id = 'r1'")
        ).one()
        plan = connection.execute(
            text("SELECT schema_version FROM meal_plans LIMIT 1")
        ).one()
    assert recipe.servings == 1.0
    assert recipe.nutrition_basis == "per_serving"
    assert plan.schema_version == "2"
