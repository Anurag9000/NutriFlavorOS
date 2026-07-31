"""SQLAlchemy persistence for reviewed recipe preparation evidence."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)

from backend.database import Base, utcnow


class DBRecipePreparationProfile(Base):
    __tablename__ = "recipe_preparation_profiles"
    __table_args__ = (
        UniqueConstraint("recipe_id", name="uq_recipe_preparation_profile_recipe"),
        CheckConstraint(
            "evidence_status IN ('draft','external_unverified','reviewed')",
            name="ck_recipe_preparation_profile_status",
        ),
        CheckConstraint(
            "schema_version <> ''",
            name="ck_recipe_preparation_profile_schema_version",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(
        String,
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_version = Column(String, nullable=False, default="1")
    task_templates = Column(JSON, nullable=False, default=list)
    source_name = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    source_version = Column(String, nullable=False)
    evidence_status = Column(String, nullable=False, default="draft", index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
