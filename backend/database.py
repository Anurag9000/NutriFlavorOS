"""Database schema and session management.

SQLite remains available for local development, while hosted deployments should
use PostgreSQL. Compatibility migrations below are intentionally additive and
idempotent; Alembic remains the required path for production migrations.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Generator

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
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
    """Authenticated user and their meal-planning profile."""

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

    plans = relationship(
        "DBMealPlan",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DBRecipe(Base):
    """Recipe data with normalized ingredient and provenance metadata."""

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
    """Versioned snapshots of generated meal plans."""

    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    schema_version = Column(String, nullable=False, default=CURRENT_PLAN_SCHEMA_VERSION)
    plan_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    user = relationship("DBUser", back_populates="plans")


class DBFeedback(Base):
    """Append-only user feedback captured for offline, reviewed training pipelines."""

    __tablename__ = "feedback_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_type = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


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


def init_db() -> None:
    """Create tables and apply additive local SQLite compatibility migrations."""

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_table("users", _SQLITE_USER_MIGRATIONS)
    _migrate_sqlite_table("recipes", _SQLITE_RECIPE_MIGRATIONS)
    _migrate_sqlite_table("meal_plans", _SQLITE_PLAN_MIGRATIONS)
    _backfill_sqlite_defaults()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that always closes the request-scoped session."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
