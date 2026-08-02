"""ORM extensions for household meal-plan approval and transition evidence.

The original ``DBMealPlan`` mapping predates the lifecycle columns added by
migration ``20260802_0013``. Declarative mappings support appending columns to
an already declared class; importing this module keeps legacy imports stable
while exposing the reviewed lifecycle everywhere services are loaded.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)

from backend.database import Base, DBMealPlan, utcnow


if not hasattr(DBMealPlan, "version"):
    DBMealPlan.version = Column(Integer, nullable=False, default=1)
    DBMealPlan.status = Column(String(32), nullable=False, default="draft")
    DBMealPlan.approved_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    DBMealPlan.approved_at = Column(DateTime(timezone=True), nullable=True)
    DBMealPlan.cancelled_at = Column(DateTime(timezone=True), nullable=True)
    DBMealPlan.cancellation_reason = Column(String(1000), nullable=True)
    DBMealPlan.updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
    DBMealPlan.__table__.append_constraint(
        CheckConstraint("version >= 1", name="ck_meal_plan_version_positive")
    )
    DBMealPlan.__table__.append_constraint(
        CheckConstraint(
            "status IN ('draft','approved','cancelled')",
            name="ck_meal_plan_valid_status",
        )
    )
    DBMealPlan.__table__.append_constraint(
        CheckConstraint(
            "((approved_by_user_id IS NULL AND approved_at IS NULL) OR "
            "(approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL))",
            name="ck_meal_plan_approval_pair",
        )
    )
    DBMealPlan.__table__.append_constraint(
        CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL "
            "AND approved_at IS NULL AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) OR "
            "(status = 'approved' AND approved_by_user_id IS NOT NULL "
            "AND approved_at IS NOT NULL AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL "
            "AND cancellation_reason IS NOT NULL)",
            name="ck_meal_plan_state_fields",
        )
    )
    Index(
        "ix_meal_plans_household_status_created",
        DBMealPlan.__table__.c.household_id,
        DBMealPlan.__table__.c.status,
        DBMealPlan.__table__.c.created_at,
    )


class DBHouseholdPlanEvent(Base):
    __tablename__ = "household_plan_events"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "idempotency_key",
            name="uq_household_plan_event_idempotency",
        ),
        CheckConstraint(
            "event_type IN ('approved','cancelled')",
            name="ck_household_plan_event_type",
        ),
        CheckConstraint(
            "from_status IN ('draft','approved')",
            name="ck_household_plan_event_from_status",
        ),
        CheckConstraint(
            "to_status IN ('approved','cancelled')",
            name="ck_household_plan_event_to_status",
        ),
        CheckConstraint(
            "(event_type = 'approved' AND from_status = 'draft' "
            "AND to_status = 'approved') OR "
            "(event_type = 'cancelled' AND from_status IN ('draft','approved') "
            "AND to_status = 'cancelled')",
            name="ck_household_plan_event_transition",
        ),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_household_plan_event_reason_nonblank",
        ),
        Index(
            "ix_household_plan_events_plan_created",
            "plan_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_household_plan_events_household_created",
            "household_id",
            "created_at",
            "id",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(
        Integer,
        ForeignKey("meal_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id = Column(
        String,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(32), nullable=False)
    actor_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status = Column(String(32), nullable=False)
    to_status = Column(String(32), nullable=False)
    reason = Column(String(1000), nullable=False)
    event_metadata = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String(200), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
