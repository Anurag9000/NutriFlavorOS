"""Database schema and session management.

SQLite remains available for local development, while hosted deployments should
use PostgreSQL. Alembic is the required production migration path. Runtime
entities use transactional tables rather than JSON files or pickle stores.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker


DB_URL = os.getenv("DATABASE_URL", "sqlite:///nutriflavor.db")
CURRENT_PLAN_SCHEMA_VERSION = "2"

_engine_kwargs = {"pool_pre_ping": True}
if DB_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DB_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DBUser(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    hashed_password = Column(String, nullable=True)
    name = Column(String, nullable=False, default="New User")
    age = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)
    gender = Column(String, nullable=True)
    activity_level = Column(Float, nullable=True)
    goal = Column(String, nullable=True)
    liked_ingredients = Column(JSON, nullable=False, default=list)
    disliked_ingredients = Column(JSON, nullable=False, default=list)
    allergies = Column(JSON, nullable=False, default=list)
    dietary_restrictions = Column(JSON, nullable=False, default=list)
    health_conditions = Column(JSON, nullable=False, default=list)
    medications = Column(JSON, nullable=False, default=list)
    target_calories = Column(Integer, nullable=True)
    target_protein_g = Column(Integer, nullable=True)
    target_carbs_g = Column(Integer, nullable=True)
    target_fat_g = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    plans = relationship("DBMealPlan", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    owned_households = relationship(
        "DBHousehold", back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )


class DBRecipe(Base):
    __tablename__ = "recipes"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=False, default="")
    image_url = Column(String)
    ingredients = Column(JSON, nullable=False, default=list)
    ingredient_data = Column(JSON, nullable=False, default=list)
    servings = Column(Float, nullable=False, default=1.0)
    calories = Column(Integer, nullable=False, default=0)
    macros = Column(JSON, nullable=False, default=dict)
    flavor_profile = Column(JSON, nullable=False, default=dict)
    tags = Column(JSON, nullable=False, default=list)
    cuisine = Column(String)
    instructions = Column(JSON, nullable=False, default=list)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    source_name = Column(String)
    source_url = Column(String)
    source_version = Column(String)
    nutrition_basis = Column(String, nullable=False, default="per_serving")


class DBMealPlan(Base):
    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    schema_version = Column(String, nullable=False, default=CURRENT_PLAN_SCHEMA_VERSION)
    plan_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    user = relationship("DBUser", back_populates="plans")


class DBFeedback(Base):
    __tablename__ = "feedback_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_type = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class DBHousehold(Base):
    __tablename__ = "households"

    id = Column(String, primary_key=True)
    owner_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner = relationship("DBUser", back_populates="owned_households")
    members = relationship("DBHouseholdMember", cascade="all, delete-orphan", passive_deletes=True)
    pantry_items = relationship("DBPantryItem", cascade="all, delete-orphan", passive_deletes=True)
    leftovers = relationship("DBLeftoverBatch", cascade="all, delete-orphan", passive_deletes=True)
    inventory_events = relationship("DBInventoryEvent", cascade="all, delete-orphan", passive_deletes=True)


class DBHouseholdMember(Base):
    __tablename__ = "household_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    display_name = Column(String, nullable=False)
    linked_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    servings_multiplier = Column(Float, nullable=False, default=1.0)
    allergies = Column(JSON, nullable=False, default=list)
    dietary_restrictions = Column(JSON, nullable=False, default=list)
    disliked_ingredients = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBPantryItem(Base):
    __tablename__ = "pantry_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_name = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    quantity_min = Column(Float, nullable=False, default=0.0)
    quantity_max = Column(Float, nullable=False, default=0.0)
    unit = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String, nullable=False, default="manual")
    item_metadata = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBLeftoverBatch(Base):
    __tablename__ = "leftover_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe_id = Column(String, ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_plan_id = Column(Integer, ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True)
    portions_available = Column(Float, nullable=False)
    cooked_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    frozen = Column(Boolean, nullable=False, default=False)
    notes = Column(String, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBInventoryEvent(Base):
    __tablename__ = "inventory_events"
    __table_args__ = (
        UniqueConstraint("household_id", "idempotency_key", name="uq_inventory_event_idempotency"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    pantry_item_id = Column(Integer, ForeignKey("pantry_items.id", ondelete="SET NULL"), nullable=True, index=True)
    leftover_id = Column(Integer, ForeignKey("leftover_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    quantity_min = Column(Float, nullable=False)
    quantity_max = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    event_metadata = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class DBExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    experiment_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    seed = Column(Integer, nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    metrics = Column(JSON, nullable=False, default=dict)
    artifact_manifest = Column(JSON, nullable=False, default=dict)
    dataset_fingerprint = Column(String, nullable=True, index=True)
    model_fingerprint = Column(String, nullable=True, index=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


_SQLITE_USER_MIGRATIONS: Dict[str, str] = {
    "hashed_password": "ALTER TABLE users ADD COLUMN hashed_password VARCHAR",
    "allergies": "ALTER TABLE users ADD COLUMN allergies JSON",
    "medications": "ALTER TABLE users ADD COLUMN medications JSON",
    "target_calories": "ALTER TABLE users ADD COLUMN target_calories INTEGER",
    "target_protein_g": "ALTER TABLE users ADD COLUMN target_protein_g INTEGER",
    "target_carbs_g": "ALTER TABLE users ADD COLUMN target_carbs_g INTEGER",
    "target_fat_g": "ALTER TABLE users ADD COLUMN target_fat_g INTEGER",
}
_SQLITE_RECIPE_MIGRATIONS: Dict[str, str] = {
    "ingredient_data": "ALTER TABLE recipes ADD COLUMN ingredient_data JSON",
    "servings": "ALTER TABLE recipes ADD COLUMN servings FLOAT",
    "source_name": "ALTER TABLE recipes ADD COLUMN source_name VARCHAR",
    "source_url": "ALTER TABLE recipes ADD COLUMN source_url VARCHAR",
    "source_version": "ALTER TABLE recipes ADD COLUMN source_version VARCHAR",
    "nutrition_basis": "ALTER TABLE recipes ADD COLUMN nutrition_basis VARCHAR",
}
_SQLITE_PLAN_MIGRATIONS: Dict[str, str] = {
    "schema_version": "ALTER TABLE meal_plans ADD COLUMN schema_version VARCHAR",
}


def _migrate_sqlite_table(table_name: str, migrations: Dict[str, str]) -> None:
    if not DB_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    statements = [sql for name, sql in migrations.items() if name not in existing]
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _backfill_sqlite_defaults() -> None:
    if not DB_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "recipes" in tables:
            columns = {column["name"] for column in inspector.get_columns("recipes")}
            if "servings" in columns:
                connection.execute(text("UPDATE recipes SET servings = 1.0 WHERE servings IS NULL OR servings <= 0"))
            if "nutrition_basis" in columns:
                connection.execute(text("UPDATE recipes SET nutrition_basis = 'per_serving' WHERE nutrition_basis IS NULL"))
        if "meal_plans" in tables:
            columns = {column["name"] for column in inspector.get_columns("meal_plans")}
            if "schema_version" in columns:
                connection.execute(
                    text("UPDATE meal_plans SET schema_version = :version WHERE schema_version IS NULL"),
                    {"version": CURRENT_PLAN_SCHEMA_VERSION},
                )


REQUIRED_RUNTIME_TABLES = {
    "users",
    "recipes",
    "meal_plans",
    "feedback_events",
    "households",
    "household_members",
    "pantry_items",
    "leftover_batches",
    "inventory_events",
    "experiment_runs",
}


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_table("users", _SQLITE_USER_MIGRATIONS)
    _migrate_sqlite_table("recipes", _SQLITE_RECIPE_MIGRATIONS)
    _migrate_sqlite_table("meal_plans", _SQLITE_PLAN_MIGRATIONS)
    _backfill_sqlite_defaults()


def verify_schema() -> None:
    missing = REQUIRED_RUNTIME_TABLES - set(inspect(engine).get_table_names())
    if missing:
        raise RuntimeError(
            "Database schema is incomplete; run `alembic upgrade head`. "
            f"Missing tables: {', '.join(sorted(missing))}"
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
