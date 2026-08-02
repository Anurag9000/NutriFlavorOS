"""Bind repair proposal semantic identity to target calendar and add ORM indexes.

Revision ID: 20260802_0016
Revises: 20260802_0015
Create Date: 2026-08-02
"""

from __future__ import annotations

from alembic import op


revision = "20260802_0016"
down_revision = "20260802_0015"
branch_labels = None
depends_on = None


PROPOSAL_INDEXES = [
    ("ix_preparation_repair_proposals_household_id", ["household_id"]),
    ("ix_preparation_repair_proposals_source_schedule_id", ["source_schedule_id"]),
    (
        "ix_preparation_repair_proposals_target_calendar_version_id",
        ["target_calendar_version_id"],
    ),
    ("ix_preparation_repair_proposals_status", ["status"]),
]

EVENT_INDEXES = [
    ("ix_preparation_repair_proposal_events_proposal_id", ["proposal_id"]),
    ("ix_preparation_repair_proposal_events_household_id", ["household_id"]),
    ("ix_preparation_repair_proposal_events_event_type", ["event_type"]),
]


def upgrade() -> None:
    with op.batch_alter_table("preparation_repair_proposals") as batch:
        batch.drop_constraint(
            "uq_preparation_repair_proposal_semantic_identity",
            type_="unique",
        )
        batch.create_unique_constraint(
            "uq_preparation_repair_proposal_semantic_identity",
            [
                "source_schedule_id",
                "source_schedule_version",
                "target_calendar_version_id",
                "revised_request_hash",
                "repaired_response_hash",
            ],
        )
    for name, columns in PROPOSAL_INDEXES:
        op.create_index(
            name,
            "preparation_repair_proposals",
            columns,
            unique=False,
        )
    for name, columns in EVENT_INDEXES:
        op.create_index(
            name,
            "preparation_repair_proposal_events",
            columns,
            unique=False,
        )


def downgrade() -> None:
    for name, _ in reversed(EVENT_INDEXES):
        op.drop_index(
            name,
            table_name="preparation_repair_proposal_events",
        )
    for name, _ in reversed(PROPOSAL_INDEXES):
        op.drop_index(
            name,
            table_name="preparation_repair_proposals",
        )
    with op.batch_alter_table("preparation_repair_proposals") as batch:
        batch.drop_constraint(
            "uq_preparation_repair_proposal_semantic_identity",
            type_="unique",
        )
        batch.create_unique_constraint(
            "uq_preparation_repair_proposal_semantic_identity",
            [
                "source_schedule_id",
                "source_schedule_version",
                "revised_request_hash",
                "repaired_response_hash",
            ],
        )
