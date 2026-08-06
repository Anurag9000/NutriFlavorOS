"""Transactional database schema and session management.

SQLite is supported for local development. Hosted and concurrent deployments
should use PostgreSQL and apply Alembic migrations before starting replicas.
Runtime user, planning, household, inventory, invitation, reservation, research,
conversion, and storage-policy state is stored transactionally.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Generator

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
CURRENT_HOUSEHOLD_PLAN_SCHEMA_VERSION = "1"

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

    plans = relationship(
        "DBMealPlan",
        back_populates="user",
        foreign_keys="DBMealPlan.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
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
    household_id = Column(
        String, ForeignKey("households.id", ondelete="SET NULL"), nullable=True, index=True
    )
    schema_version = Column(String, nullable=False, default=CURRENT_PLAN_SCHEMA_VERSION)
    plan_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    user = relationship("DBUser", back_populates="plans", foreign_keys=[user_id])


class DBFeedback(Base):
    __tablename__ = "feedback_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_type = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class DBHousehold(Base):
    __tablename__ = "households"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_household_version_positive"),
    )

    id = Column(String, primary_key=True)
    owner_user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner = relationship("DBUser", back_populates="owned_households")
    members = relationship("DBHouseholdMember", cascade="all, delete-orphan", passive_deletes=True)
    invitations = relationship(
        "DBHouseholdInvitation", cascade="all, delete-orphan", passive_deletes=True
    )
    pantry_items = relationship("DBPantryItem", cascade="all, delete-orphan", passive_deletes=True)
    leftovers = relationship(
        "DBLeftoverBatch", cascade="all, delete-orphan", passive_deletes=True
    )
    inventory_events = relationship(
        "DBInventoryEvent", cascade="all, delete-orphan", passive_deletes=True
    )
    reservations = relationship(
        "DBStockReservation", cascade="all, delete-orphan", passive_deletes=True
    )


class DBHouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (
        UniqueConstraint("household_id", "linked_user_id", name="uq_household_linked_user"),
        CheckConstraint("servings_multiplier > 0", name="ck_member_positive_servings"),
        CheckConstraint("role IN ('viewer','editor','owner')", name="ck_member_valid_role"),
        CheckConstraint(
            "target_calories IS NULL OR (target_calories > 0 AND target_calories <= 20000)",
            name="ck_member_target_calories",
        ),
        CheckConstraint(
            "target_protein_g IS NULL OR (target_protein_g >= 0 AND target_protein_g <= 2000)",
            name="ck_member_target_protein",
        ),
        CheckConstraint(
            "target_carbs_g IS NULL OR (target_carbs_g >= 0 AND target_carbs_g <= 4000)",
            name="ck_member_target_carbs",
        ),
        CheckConstraint(
            "target_fat_g IS NULL OR (target_fat_g >= 0 AND target_fat_g <= 2000)",
            name="ck_member_target_fat",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name = Column(String, nullable=False)
    linked_user_id = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role = Column(String, nullable=False, default="viewer", index=True)
    servings_multiplier = Column(Float, nullable=False, default=1.0)
    allergies = Column(JSON, nullable=False, default=list)
    dietary_restrictions = Column(JSON, nullable=False, default=list)
    disliked_ingredients = Column(JSON, nullable=False, default=list)
    target_calories = Column(Integer, nullable=True)
    target_protein_g = Column(Integer, nullable=True)
    target_carbs_g = Column(Integer, nullable=True)
    target_fat_g = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBHouseholdInvitation(Base):
    __tablename__ = "household_invitations"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_household_invitation_token_hash"),
        CheckConstraint("role IN ('viewer','editor')", name="ck_invitation_valid_role"),
        CheckConstraint(
            "accepted_at IS NULL OR revoked_at IS NULL",
            name="ck_invitation_single_terminal_state",
        ),
    )

    id = Column(String, primary_key=True)
    household_id = Column(
        String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_email = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False, default="viewer")
    token_hash = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBPantryItem(Base):
    __tablename__ = "pantry_items"
    __table_args__ = (
        CheckConstraint("quantity_min >= 0", name="ck_pantry_min_nonnegative"),
        CheckConstraint("quantity_max >= quantity_min", name="ck_pantry_valid_range"),
        CheckConstraint("version >= 1", name="ck_pantry_version_positive"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
    __table_args__ = (
        CheckConstraint("portions_available >= 0", name="ck_leftover_nonnegative"),
        CheckConstraint("version >= 1", name="ck_leftover_version_positive"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipe_id = Column(
        String, ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_plan_id = Column(
        Integer, ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True
    )
    portions_available = Column(Float, nullable=False)
    cooked_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    frozen = Column(Boolean, nullable=False, default=False)
    notes = Column(String, nullable=True)
    storage_policy_key = Column(
        String,
        ForeignKey("storage_policies.policy_key", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBInventoryEvent(Base):
    __tablename__ = "inventory_events"
    __table_args__ = (
        UniqueConstraint("household_id", "idempotency_key", name="uq_inventory_event_idempotency"),
        CheckConstraint("quantity_min >= 0", name="ck_inventory_event_min_nonnegative"),
        CheckConstraint("quantity_max >= quantity_min", name="ck_inventory_event_valid_range"),
        CheckConstraint(
            "event_type IN ('purchase','consume','adjust','discard','leftover_create','leftover_consume','reservation_commit')",
            name="ck_inventory_event_valid_type",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pantry_item_id = Column(
        Integer, ForeignKey("pantry_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    leftover_id = Column(
        Integer, ForeignKey("leftover_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type = Column(String, nullable=False, index=True)
    quantity_min = Column(Float, nullable=False)
    quantity_max = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    event_metadata = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class DBStockReservation(Base):
    __tablename__ = "stock_reservations"
    __table_args__ = (
        UniqueConstraint("plan_id", "pantry_item_id", name="uq_plan_pantry_reservation"),
        CheckConstraint("quantity_min >= 0", name="ck_reservation_min_nonnegative"),
        CheckConstraint("quantity_max >= quantity_min", name="ck_reservation_valid_range"),
        CheckConstraint(
            "status IN ('active','released','consumed','expired')",
            name="ck_reservation_valid_status",
        ),
        CheckConstraint("version >= 1", name="ck_reservation_version_positive"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        String, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pantry_item_id = Column(
        Integer, ForeignKey("pantry_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    plan_id = Column(
        Integer, ForeignKey("meal_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_name = Column(String, nullable=False, index=True)
    quantity_min = Column(Float, nullable=False)
    quantity_max = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active", index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class DBIngredientConversion(Base):
    __tablename__ = "ingredient_conversions"
    __table_args__ = (
        UniqueConstraint(
            "canonical_name",
            "from_unit",
            "to_unit",
            "source_name",
            "source_version",
            name="uq_conversion_evidence",
        ),
        CheckConstraint("multiplier_min > 0", name="ck_conversion_min_positive"),
        CheckConstraint("multiplier_max >= multiplier_min", name="ck_conversion_valid_range"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(String, nullable=False, index=True)
    from_unit = Column(String, nullable=False)
    to_unit = Column(String, nullable=False)
    multiplier_min = Column(Float, nullable=False)
    multiplier_max = Column(Float, nullable=False)
    source_name = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    source_version = Column(String, nullable=False)
    evidence_status = Column(String, nullable=False, default="external_unverified")
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True)


class DBStoragePolicy(Base):
    __tablename__ = "storage_policies"
    __table_args__ = (
        UniqueConstraint("policy_key", name="uq_storage_policy_key"),
        CheckConstraint(
            "duration_max_hours IS NULL OR duration_min_hours IS NULL OR "
            "duration_max_hours >= duration_min_hours",
            name="ck_storage_policy_valid_duration",
        ),
        CheckConstraint(
            "duration_min_hours IS NULL OR duration_min_hours >= 0",
            name="ck_storage_policy_min_nonnegative",
        ),
        CheckConstraint(
            "duration_max_hours IS NULL OR duration_max_hours >= 0",
            name="ck_storage_policy_max_nonnegative",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_key = Column(String, nullable=False, index=True)
    food_category = Column(String, nullable=False, index=True)
    storage_state = Column(String, nullable=False, index=True)
    duration_min_hours = Column(Float, nullable=True)
    duration_max_hours = Column(Float, nullable=True)
    maximum_temperature_c = Column(Float, nullable=True)
    source_name = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=False)
    safety_scope = Column(String, nullable=False, default="general_guidance")
    notes = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True)


class DBExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id = Column(String, primary_key=True)
    user_id = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
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
    "household_id": "ALTER TABLE meal_plans ADD COLUMN household_id VARCHAR",
}
_SQLITE_MEMBER_MIGRATIONS: Dict[str, str] = {
    "role": "ALTER TABLE household_members ADD COLUMN role VARCHAR",
    "target_calories": "ALTER TABLE household_members ADD COLUMN target_calories INTEGER",
    "target_protein_g": "ALTER TABLE household_members ADD COLUMN target_protein_g INTEGER",
    "target_carbs_g": "ALTER TABLE household_members ADD COLUMN target_carbs_g INTEGER",
    "target_fat_g": "ALTER TABLE household_members ADD COLUMN target_fat_g INTEGER",
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
                connection.execute(
                    text("UPDATE recipes SET servings = 1.0 WHERE servings IS NULL OR servings <= 0")
                )
            if "nutrition_basis" in columns:
                connection.execute(
                    text(
                        "UPDATE recipes SET nutrition_basis = 'per_serving' "
                        "WHERE nutrition_basis IS NULL"
                    )
                )
        if "meal_plans" in tables:
            columns = {column["name"] for column in inspector.get_columns("meal_plans")}
            if "schema_version" in columns:
                connection.execute(
                    text(
                        "UPDATE meal_plans SET schema_version = :version "
                        "WHERE schema_version IS NULL"
                    ),
                    {"version": CURRENT_PLAN_SCHEMA_VERSION},
                )
        if "household_members" in tables:
            columns = {
                column["name"] for column in inspector.get_columns("household_members")
            }
            if "role" in columns:
                connection.execute(
                    text(
                        "UPDATE household_members SET role = CASE "
                        "WHEN linked_user_id IN "
                        "(SELECT owner_user_id FROM households "
                        "WHERE households.id = household_members.household_id) "
                        "THEN 'owner' ELSE 'viewer' END "
                        "WHERE role IS NULL"
                    )
                )


REQUIRED_RUNTIME_TABLES = {
    "users",
    "recipes",
    "meal_plans",
    "feedback_events",
    "households",
    "household_members",
    "household_invitations",
    "pantry_items",
    "leftover_batches",
    "inventory_events",
    "stock_reservations",
    "ingredient_conversions",
    "storage_policies",
    "experiment_runs",
}


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_table("users", _SQLITE_USER_MIGRATIONS)
    _migrate_sqlite_table("recipes", _SQLITE_RECIPE_MIGRATIONS)
    _migrate_sqlite_table("meal_plans", _SQLITE_PLAN_MIGRATIONS)
    _migrate_sqlite_table("household_members", _SQLITE_MEMBER_MIGRATIONS)
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
