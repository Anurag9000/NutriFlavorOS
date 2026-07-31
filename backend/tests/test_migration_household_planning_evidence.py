import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_revision_upgrades_previous_household_schema(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'legacy.db'}")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE users (id VARCHAR PRIMARY KEY)")); c.execute(text("CREATE TABLE households (id VARCHAR PRIMARY KEY, owner_user_id VARCHAR)"))
        c.execute(text("CREATE TABLE household_members (id INTEGER PRIMARY KEY, household_id VARCHAR, display_name VARCHAR, linked_user_id VARCHAR, servings_multiplier FLOAT, allergies JSON, dietary_restrictions JSON, disliked_ingredients JSON, active BOOLEAN, created_at DATETIME)"))
        c.execute(text("CREATE TABLE meal_plans (id INTEGER PRIMARY KEY, user_id VARCHAR, schema_version VARCHAR, plan_data JSON, created_at DATETIME)"))
        c.execute(text("CREATE TABLE pantry_items (id INTEGER PRIMARY KEY, household_id VARCHAR, canonical_name VARCHAR, display_name VARCHAR, quantity_min FLOAT, quantity_max FLOAT, unit VARCHAR, expires_at DATETIME, opened_at DATETIME, source VARCHAR, item_metadata JSON, version INTEGER, created_at DATETIME, updated_at DATETIME)"))
        c.execute(text("CREATE TABLE leftover_batches (id INTEGER PRIMARY KEY, household_id VARCHAR, recipe_id VARCHAR, source_plan_id INTEGER, portions_available FLOAT, cooked_at DATETIME, expires_at DATETIME, frozen BOOLEAN, notes VARCHAR, version INTEGER, created_at DATETIME, updated_at DATETIME)"))
        c.execute(text("INSERT INTO users VALUES ('o@example.com')")); c.execute(text("INSERT INTO households VALUES ('h','o@example.com')")); c.execute(text("INSERT INTO household_members VALUES (1,'h','Owner','o@example.com',1,'[]','[]','[]',1,NULL)"))
        context=MigrationContext.configure(c); operations=Operations(context)
        path=Path(__file__).resolve().parents[1]/"migrations"/"versions"/"20260731_0003_household_planning_evidence.py"
        spec=importlib.util.spec_from_file_location("migration_0003",path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.op=operations; module.upgrade()
    inspector=inspect(engine)
    assert {"household_invitations","stock_reservations","ingredient_conversions","storage_policies"}.issubset(inspector.get_table_names())
    assert {"role","target_calories"}.issubset({x['name'] for x in inspector.get_columns('household_members')})
    assert "household_id" in {x['name'] for x in inspector.get_columns('meal_plans')}
