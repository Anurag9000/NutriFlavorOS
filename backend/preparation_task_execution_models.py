"""Persistence model for user-confirmed preparation task execution events."""

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
    Text,
    UniqueConstraint,
)

from backend.database import Base, utcnow


class DBPreparationTaskExecutionEvent(Base):
    __tablename__ = "preparation_task_execution_events"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id",
            "idempotency_key",
            name="uq_preparation_task_event_schedule_idempotency",
        ),
        CheckConstraint(
            "length(trim(task_id)) > 0",
            name="ck_preparation_task_event_task_nonblank",
        ),
        CheckConstraint(
            "event_type IN ('started','completed','skipped')",
            name="ck_preparation_task_event_type",
        ),
        CheckConstraint(
            "from_state IN ('planned','in_progress')",
            name="ck_preparation_task_event_from_state",
        ),
        CheckConstraint(
            "to_state IN ('in_progress','completed','skipped')",
            name="ck_preparation_task_event_to_state",
        ),
        CheckConstraint(
            "(event_type = 'started' AND from_state = 'planned' "
            "AND to_state = 'in_progress') OR "
            "(event_type = 'completed' AND from_state = 'in_progress' "
            "AND to_state = 'completed') OR "
            "(event_type = 'skipped' AND from_state IN ('planned','in_progress') "
            "AND to_state = 'skipped')",
            name="ck_preparation_task_event_transition",
        ),
        CheckConstraint(
            "planned_start_minute >= 0 AND planned_start_minute <= 10080 "
            "AND planned_finish_minute > planned_start_minute "
            "AND planned_finish_minute <= 10080",
            name="ck_preparation_task_event_planned_bounds",
        ),
        CheckConstraint(
            "actual_minute >= 0 AND actual_minute <= 10080",
            name="ck_preparation_task_event_actual_bounds",
        ),
        CheckConstraint(
            "(event_type = 'started' "
            "AND deviation_minutes = actual_minute - planned_start_minute) OR "
            "(event_type = 'completed' "
            "AND deviation_minutes = actual_minute - planned_finish_minute) OR "
            "(event_type = 'skipped' AND deviation_minutes = 0)",
            name="ck_preparation_task_event_deviation",
        ),
        CheckConstraint(
            "((event_type = 'skipped' OR deviation_minutes <> 0) "
            "AND reason IS NOT NULL AND length(trim(reason)) > 0) OR "
            "(event_type IN ('started','completed') AND deviation_minutes = 0)",
            name="ck_preparation_task_event_reason_required",
        ),
        CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_preparation_task_event_fingerprint_length",
        ),
        CheckConstraint(
            "schedule_version_before >= 1 "
            "AND schedule_version_after = schedule_version_before + 1",
            name="ck_preparation_task_event_schedule_versions",
        ),
        Index(
            "ix_preparation_task_events_schedule_created",
            "schedule_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_preparation_task_events_schedule_task_created",
            "schedule_id",
            "task_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_preparation_task_events_household_created",
            "household_id",
            "created_at",
            "id",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(
        Integer,
        ForeignKey("persisted_preparation_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id = Column(
        String,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id = Column(String(160), nullable=False)
    event_type = Column(String(32), nullable=False)
    actor_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_state = Column(String(32), nullable=False)
    to_state = Column(String(32), nullable=False)
    planned_start_minute = Column(Integer, nullable=False)
    planned_finish_minute = Column(Integer, nullable=False)
    actual_minute = Column(Integer, nullable=False)
    deviation_minutes = Column(Integer, nullable=False)
    reason = Column(String(1000), nullable=True)
    notes = Column(Text, nullable=True)
    event_metadata = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String(240), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    schedule_version_before = Column(Integer, nullable=False)
    schedule_version_after = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
