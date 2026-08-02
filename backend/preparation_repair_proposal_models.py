"""Persistence models for preparation repair proposals and acceptance evidence."""

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


class DBPreparationRepairProposal(Base):
    __tablename__ = "preparation_repair_proposals"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "creation_idempotency_key",
            name="uq_preparation_repair_proposal_household_idempotency",
        ),
        CheckConstraint(
            "status IN ('proposed','accepted','rejected','invalidated')",
            name="ck_preparation_repair_proposal_status",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_preparation_repair_proposal_version_positive",
        ),
        CheckConstraint(
            "length(source_schedule_hash) = 64",
            name="ck_preparation_repair_proposal_source_hash_length",
        ),
        CheckConstraint(
            "length(source_schedule_request_hash) = 64",
            name="ck_preparation_repair_proposal_source_request_hash_length",
        ),
        CheckConstraint(
            "length(target_calendar_content_hash) = 64",
            name="ck_preparation_repair_proposal_calendar_hash_length",
        ),
        CheckConstraint(
            "length(repair_request_hash) = 64",
            name="ck_preparation_repair_proposal_request_hash_length",
        ),
        CheckConstraint(
            "length(repair_result_hash) = 64",
            name="ck_preparation_repair_proposal_result_hash_length",
        ),
        CheckConstraint(
            "length(revised_request_hash) = 64",
            name="ck_preparation_repair_proposal_revised_hash_length",
        ),
        CheckConstraint(
            "length(repaired_response_hash) = 64",
            name="ck_preparation_repair_proposal_response_hash_length",
        ),
        CheckConstraint(
            "length(creation_request_fingerprint) = 64",
            name="ck_preparation_repair_proposal_fingerprint_length",
        ),
        CheckConstraint(
            "((status = 'rejected' AND rejected_by_user_id IS NOT NULL "
            "AND rejected_at IS NOT NULL AND rejection_reason IS NOT NULL "
            "AND length(trim(rejection_reason)) > 0) OR "
            "(status <> 'rejected' AND rejected_by_user_id IS NULL "
            "AND rejected_at IS NULL AND rejection_reason IS NULL))",
            name="ck_preparation_repair_proposal_rejection_state",
        ),
        Index(
            "ix_preparation_repair_proposals_household_status_updated",
            "household_id",
            "status",
            "updated_at",
        ),
        Index(
            "ix_preparation_repair_proposals_source_schedule",
            "source_schedule_id",
            "source_schedule_version",
        ),
        Index(
            "ix_preparation_repair_proposals_semantic_hashes",
            "source_schedule_id",
            "source_schedule_version",
            "target_calendar_version_id",
            "revised_request_hash",
            "repaired_response_hash",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        String,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_schedule_id = Column(
        Integer,
        ForeignKey("persisted_preparation_schedules.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_schedule_version = Column(Integer, nullable=False)
    source_schedule_hash = Column(String(64), nullable=False)
    source_schedule_request_hash = Column(String(64), nullable=False)
    target_calendar_version_id = Column(
        Integer,
        ForeignKey("resource_calendar_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    target_calendar_content_hash = Column(String(64), nullable=False)
    repair_request_payload = Column(JSON, nullable=False)
    repair_request_hash = Column(String(64), nullable=False, index=True)
    repair_result_payload = Column(JSON, nullable=False)
    repair_result_hash = Column(String(64), nullable=False, index=True)
    revised_request_hash = Column(String(64), nullable=False, index=True)
    repaired_response_hash = Column(String(64), nullable=False, index=True)
    required_acknowledgement_task_ids = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="proposed", index=True)
    version = Column(Integer, nullable=False, default=1)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rejected_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    creation_idempotency_key = Column(String(240), nullable=False)
    creation_request_fingerprint = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DBPreparationRepairProposalEvent(Base):
    __tablename__ = "preparation_repair_proposal_events"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            "idempotency_key",
            name="uq_preparation_repair_event_proposal_idempotency",
        ),
        CheckConstraint(
            "event_type IN ('created','accepted','rejected','invalidated')",
            name="ck_preparation_repair_event_type",
        ),
        CheckConstraint(
            "to_status IN ('proposed','accepted','rejected','invalidated')",
            name="ck_preparation_repair_event_to_status",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('proposed','accepted','rejected','invalidated')",
            name="ck_preparation_repair_event_from_status",
        ),
        CheckConstraint(
            "((event_type = 'created' AND from_status IS NULL "
            "AND to_status = 'proposed') OR "
            "(event_type = 'accepted' AND from_status = 'proposed' "
            "AND to_status = 'accepted') OR "
            "(event_type = 'rejected' AND from_status = 'proposed' "
            "AND to_status = 'rejected') OR "
            "(event_type = 'invalidated' AND from_status = 'proposed' "
            "AND to_status = 'invalidated'))",
            name="ck_preparation_repair_event_transition",
        ),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_preparation_repair_event_reason_nonblank",
        ),
        CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_preparation_repair_event_fingerprint_length",
        ),
        CheckConstraint(
            "proposal_version_before >= 0 "
            "AND proposal_version_after = proposal_version_before + 1",
            name="ck_preparation_repair_event_versions",
        ),
        Index(
            "ix_preparation_repair_events_proposal_created",
            "proposal_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_preparation_repair_events_household_created",
            "household_id",
            "created_at",
            "id",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(
        Integer,
        ForeignKey("preparation_repair_proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    household_id = Column(
        String,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(32), nullable=False, index=True)
    actor_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)
    reason = Column(Text, nullable=False)
    event_metadata = Column(JSON, nullable=False, default=dict)
    proposal_version_before = Column(Integer, nullable=False)
    proposal_version_after = Column(Integer, nullable=False)
    idempotency_key = Column(String(240), nullable=False)
    request_fingerprint = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DBPreparationRepairProposalAcceptance(Base):
    __tablename__ = "preparation_repair_proposal_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            name="uq_preparation_repair_acceptance_proposal",
        ),
        UniqueConstraint(
            "source_schedule_id",
            "source_schedule_version",
            name="uq_preparation_repair_acceptance_source_version",
        ),
        UniqueConstraint(
            "created_schedule_id",
            name="uq_preparation_repair_acceptance_schedule",
        ),
        UniqueConstraint(
            "household_id",
            "idempotency_key",
            name="uq_preparation_repair_acceptance_household_idempotency",
        ),
        CheckConstraint(
            "proposal_version_before >= 1 "
            "AND proposal_version_after = proposal_version_before + 1",
            name="ck_preparation_repair_acceptance_versions",
        ),
        CheckConstraint(
            "created_schedule_version = 1",
            name="ck_preparation_repair_acceptance_schedule_version",
        ),
        CheckConstraint(
            "derivation_method = "
            "'deterministic_minimal_change_preparation_repair_v1'",
            name="ck_preparation_repair_acceptance_method",
        ),
        CheckConstraint(
            "length(source_schedule_hash) = 64 "
            "AND length(source_schedule_request_hash) = 64 "
            "AND length(target_calendar_content_hash) = 64 "
            "AND length(repair_request_hash) = 64 "
            "AND length(repair_result_hash) = 64 "
            "AND length(revised_request_hash) = 64 "
            "AND length(repaired_response_hash) = 64 "
            "AND length(request_fingerprint) = 64",
            name="ck_preparation_repair_acceptance_hash_lengths",
        ),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_preparation_repair_acceptance_reason_nonblank",
        ),
        Index(
            "ix_preparation_repair_acceptances_household_created",
            "household_id",
            "created_at",
            "id",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        String,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposal_id = Column(
        Integer,
        ForeignKey("preparation_repair_proposals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    proposal_version_before = Column(Integer, nullable=False)
    proposal_version_after = Column(Integer, nullable=False)
    source_schedule_id = Column(
        Integer,
        ForeignKey("persisted_preparation_schedules.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_schedule_version = Column(Integer, nullable=False)
    created_schedule_id = Column(
        Integer,
        ForeignKey("persisted_preparation_schedules.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_schedule_version = Column(Integer, nullable=False, default=1)
    derivation_method = Column(String(96), nullable=False)
    source_schedule_hash = Column(String(64), nullable=False)
    source_schedule_request_hash = Column(String(64), nullable=False)
    target_calendar_content_hash = Column(String(64), nullable=False)
    repair_request_hash = Column(String(64), nullable=False)
    repair_result_hash = Column(String(64), nullable=False)
    revised_request_hash = Column(String(64), nullable=False)
    repaired_response_hash = Column(String(64), nullable=False)
    acknowledged_task_ids = Column(JSON, nullable=False, default=list)
    reason = Column(Text, nullable=False)
    actor_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    acceptance_metadata = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String(240), nullable=False)
    request_fingerprint = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
