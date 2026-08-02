"""Add method-aware accepted repaired draft persistence.

Revision ID: 20260802_0017
Revises: 20260802_0016
Create Date: 2026-08-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260802_0017"
down_revision = "20260802_0016"
branch_labels = None
depends_on = None


ORIGINAL_METHOD = "deterministic_dependency_aware_resource_scheduler_v2"
REPAIR_METHOD = "deterministic_minimal_change_preparation_repair_v1"


def upgrade() -> None:
    with op.batch_alter_table("preparation_repair_proposals") as batch:
        batch.drop_constraint(
            "ck_preparation_repair_proposal_status",
            type_="check",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_proposal_status",
            "status IN ('proposed','accepted','rejected','invalidated')",
        )

    with op.batch_alter_table("preparation_repair_proposal_events") as batch:
        batch.drop_constraint(
            "ck_preparation_repair_event_type",
            type_="check",
        )
        batch.drop_constraint(
            "ck_preparation_repair_event_to_status",
            type_="check",
        )
        batch.drop_constraint(
            "ck_preparation_repair_event_from_status",
            type_="check",
        )
        batch.drop_constraint(
            "ck_preparation_repair_event_transition",
            type_="check",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_event_type",
            "event_type IN ('created','accepted','rejected','invalidated')",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_event_to_status",
            "to_status IN ('proposed','accepted','rejected','invalidated')",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_event_from_status",
            "from_status IS NULL OR from_status IN "
            "('proposed','accepted','rejected','invalidated')",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_event_transition",
            "((event_type = 'created' AND from_status IS NULL "
            "AND to_status = 'proposed') OR "
            "(event_type = 'accepted' AND from_status = 'proposed' "
            "AND to_status = 'accepted') OR "
            "(event_type = 'rejected' AND from_status = 'proposed' "
            "AND to_status = 'rejected') OR "
            "(event_type = 'invalidated' AND from_status = 'proposed' "
            "AND to_status = 'invalidated'))",
        )

    with op.batch_alter_table("persisted_preparation_schedules") as batch:
        batch.add_column(
            sa.Column(
                "derivation_method",
                sa.String(length=96),
                nullable=False,
                server_default=ORIGINAL_METHOD,
            )
        )
        batch.add_column(
            sa.Column("source_repair_proposal_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("source_repair_proposal_version", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("source_repair_request_hash", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column("source_repair_result_hash", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column("source_revised_request_hash", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column("source_repaired_response_hash", sa.String(length=64), nullable=True)
        )
        batch.create_foreign_key(
            "fk_persisted_schedule_source_repair_proposal",
            "preparation_repair_proposals",
            ["source_repair_proposal_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint(
            "uq_persisted_schedule_source_repair_proposal",
            ["source_repair_proposal_id"],
        )
        batch.create_check_constraint(
            "ck_persisted_schedule_derivation_method",
            "derivation_method IN ("
            f"'{ORIGINAL_METHOD}','{REPAIR_METHOD}')",
        )
        batch.create_check_constraint(
            "ck_persisted_schedule_repair_derivation_evidence",
            "((derivation_method = "
            f"'{ORIGINAL_METHOD}' "
            "AND source_repair_proposal_id IS NULL "
            "AND source_repair_proposal_version IS NULL "
            "AND source_repair_request_hash IS NULL "
            "AND source_repair_result_hash IS NULL "
            "AND source_revised_request_hash IS NULL "
            "AND source_repaired_response_hash IS NULL) OR "
            "(derivation_method = "
            f"'{REPAIR_METHOD}' "
            "AND source_repair_proposal_id IS NOT NULL "
            "AND source_repair_proposal_version IS NOT NULL "
            "AND length(source_repair_request_hash) = 64 "
            "AND length(source_repair_result_hash) = 64 "
            "AND length(source_revised_request_hash) = 64 "
            "AND length(source_repaired_response_hash) = 64))",
        )

    op.create_index(
        "ix_persisted_preparation_schedules_derivation_method",
        "persisted_preparation_schedules",
        ["derivation_method"],
        unique=False,
    )
    op.create_index(
        "ix_persisted_preparation_schedules_source_repair_proposal_id",
        "persisted_preparation_schedules",
        ["source_repair_proposal_id"],
        unique=False,
    )
    op.create_index(
        "ix_persisted_schedule_derivation_created",
        "persisted_preparation_schedules",
        ["derivation_method", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "preparation_repair_proposal_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "household_id",
            sa.String(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "proposal_id",
            sa.Integer(),
            sa.ForeignKey("preparation_repair_proposals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("proposal_version_before", sa.Integer(), nullable=False),
        sa.Column("proposal_version_after", sa.Integer(), nullable=False),
        sa.Column(
            "source_schedule_id",
            sa.Integer(),
            sa.ForeignKey("persisted_preparation_schedules.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_schedule_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_schedule_id",
            sa.Integer(),
            sa.ForeignKey("persisted_preparation_schedules.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_schedule_version", sa.Integer(), nullable=False),
        sa.Column("derivation_method", sa.String(length=96), nullable=False),
        sa.Column("source_schedule_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "source_schedule_request_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "target_calendar_content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("repair_request_hash", sa.String(length=64), nullable=False),
        sa.Column("repair_result_hash", sa.String(length=64), nullable=False),
        sa.Column("revised_request_hash", sa.String(length=64), nullable=False),
        sa.Column("repaired_response_hash", sa.String(length=64), nullable=False),
        sa.Column("acknowledged_task_ids", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("acceptance_metadata", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "proposal_id",
            name="uq_preparation_repair_acceptance_proposal",
        ),
        sa.UniqueConstraint(
            "created_schedule_id",
            name="uq_preparation_repair_acceptance_schedule",
        ),
        sa.UniqueConstraint(
            "household_id",
            "idempotency_key",
            name="uq_preparation_repair_acceptance_household_idempotency",
        ),
        sa.CheckConstraint(
            "proposal_version_before >= 1 "
            "AND proposal_version_after = proposal_version_before + 1",
            name="ck_preparation_repair_acceptance_versions",
        ),
        sa.CheckConstraint(
            "created_schedule_version = 1",
            name="ck_preparation_repair_acceptance_schedule_version",
        ),
        sa.CheckConstraint(
            f"derivation_method = '{REPAIR_METHOD}'",
            name="ck_preparation_repair_acceptance_method",
        ),
        sa.CheckConstraint(
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
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_preparation_repair_acceptance_reason_nonblank",
        ),
    )
    op.create_index(
        "ix_preparation_repair_proposal_acceptances_household_id",
        "preparation_repair_proposal_acceptances",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposal_acceptances_proposal_id",
        "preparation_repair_proposal_acceptances",
        ["proposal_id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposal_acceptances_source_schedule_id",
        "preparation_repair_proposal_acceptances",
        ["source_schedule_id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposal_acceptances_created_schedule_id",
        "preparation_repair_proposal_acceptances",
        ["created_schedule_id"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_proposal_acceptances_request_fingerprint",
        "preparation_repair_proposal_acceptances",
        ["request_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_preparation_repair_acceptances_household_created",
        "preparation_repair_proposal_acceptances",
        ["household_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    connection = op.get_bind()
    acceptance_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM preparation_repair_proposal_acceptances")
    ).scalar_one()
    repaired_schedule_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM persisted_preparation_schedules "
            "WHERE derivation_method = :method"
        ),
        {"method": REPAIR_METHOD},
    ).scalar_one()
    accepted_proposal_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM preparation_repair_proposals "
            "WHERE status = 'accepted'"
        )
    ).scalar_one()
    if acceptance_count or repaired_schedule_count or accepted_proposal_count:
        raise RuntimeError(
            "Cannot downgrade repair acceptance migration while accepted repair "
            "evidence or repaired schedules exist"
        )

    for name in [
        "ix_preparation_repair_acceptances_household_created",
        "ix_preparation_repair_proposal_acceptances_request_fingerprint",
        "ix_preparation_repair_proposal_acceptances_created_schedule_id",
        "ix_preparation_repair_proposal_acceptances_source_schedule_id",
        "ix_preparation_repair_proposal_acceptances_proposal_id",
        "ix_preparation_repair_proposal_acceptances_household_id",
    ]:
        op.drop_index(
            name,
            table_name="preparation_repair_proposal_acceptances",
        )
    op.drop_table("preparation_repair_proposal_acceptances")

    for name in [
        "ix_persisted_schedule_derivation_created",
        "ix_persisted_preparation_schedules_source_repair_proposal_id",
        "ix_persisted_preparation_schedules_derivation_method",
    ]:
        op.drop_index(name, table_name="persisted_preparation_schedules")

    with op.batch_alter_table("persisted_preparation_schedules") as batch:
        batch.drop_constraint(
            "ck_persisted_schedule_repair_derivation_evidence",
            type_="check",
        )
        batch.drop_constraint(
            "ck_persisted_schedule_derivation_method",
            type_="check",
        )
        batch.drop_constraint(
            "uq_persisted_schedule_source_repair_proposal",
            type_="unique",
        )
        batch.drop_constraint(
            "fk_persisted_schedule_source_repair_proposal",
            type_="foreignkey",
        )
        batch.drop_column("source_repaired_response_hash")
        batch.drop_column("source_revised_request_hash")
        batch.drop_column("source_repair_result_hash")
        batch.drop_column("source_repair_request_hash")
        batch.drop_column("source_repair_proposal_version")
        batch.drop_column("source_repair_proposal_id")
        batch.drop_column("derivation_method")

    with op.batch_alter_table("preparation_repair_proposal_events") as batch:
        batch.drop_constraint(
            "ck_preparation_repair_event_transition",
            type_="check",
        )
        batch.drop_constraint(
            "ck_preparation_repair_event_from_status",
            type_="check",
        )
        batch.drop_constraint(
            "ck_preparation_repair_event_to_status",
            type_="check",
        )
        batch.drop_constraint(
            "ck_preparation_repair_event_type",
            type_="check",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_event_type",
            "event_type IN ('created','rejected','invalidated')",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_event_to_status",
            "to_status IN ('proposed','rejected','invalidated')",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_event_from_status",
            "from_status IS NULL OR from_status IN "
            "('proposed','rejected','invalidated')",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_event_transition",
            "((event_type = 'created' AND from_status IS NULL "
            "AND to_status = 'proposed') OR "
            "(event_type = 'rejected' AND from_status = 'proposed' "
            "AND to_status = 'rejected') OR "
            "(event_type = 'invalidated' AND from_status = 'proposed' "
            "AND to_status = 'invalidated'))",
        )

    with op.batch_alter_table("preparation_repair_proposals") as batch:
        batch.drop_constraint(
            "ck_preparation_repair_proposal_status",
            type_="check",
        )
        batch.create_check_constraint(
            "ck_preparation_repair_proposal_status",
            "status IN ('proposed','rejected','invalidated')",
        )
