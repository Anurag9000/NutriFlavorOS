"""SQLAlchemy persistence for reviewed recipe preparation evidence."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)

from backend.database import Base, utcnow


class DBRecipePreparationProfile(Base):
    __tablename__ = "recipe_preparation_profiles"
    __table_args__ = (
        UniqueConstraint(
            "recipe_id",
            "profile_version",
            name="uq_recipe_preparation_profile_version",
        ),
        CheckConstraint(
            "evidence_status IN ('draft','external_unverified','reviewed')",
            name="ck_recipe_preparation_profile_status",
        ),
        CheckConstraint(
            "schema_version <> ''",
            name="ck_recipe_preparation_profile_schema_version",
        ),
        CheckConstraint(
            "profile_version <> ''",
            name="ck_recipe_preparation_profile_version_nonempty",
        ),
        CheckConstraint(
            "supported_servings_min > 0",
            name="ck_recipe_preparation_profile_servings_min",
        ),
        CheckConstraint(
            "supported_servings_max >= supported_servings_min",
            name="ck_recipe_preparation_profile_servings_range",
        ),
        Index(
            "uq_active_reviewed_preparation_profile_recipe",
            "recipe_id",
            unique=True,
            sqlite_where=text("active = 1 AND evidence_status = 'reviewed'"),
            postgresql_where=text("active AND evidence_status = 'reviewed'"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(
        String,
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_version = Column(String, nullable=False)
    schema_version = Column(String, nullable=False, default="1")
    supported_servings_min = Column(Float, nullable=False)
    supported_servings_max = Column(Float, nullable=False)
    task_templates = Column(JSON, nullable=False, default=list)
    source_name = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    source_version = Column(String, nullable=False)
    evidence_status = Column(String, nullable=False, default="draft", index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    supersedes_profile_id = Column(
        Integer,
        ForeignKey("recipe_preparation_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
