"""Read-only, hash-addressed support export for preparation schedules."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from backend.domain.preparation_operations import PersistedPreparationScheduleView
from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptanceView,
    PreparationRepairProposalStatus,
)
from backend.domain.preparation_schedule_support_export import (
    PreparationScheduleSupportExport,
)
from backend.preparation_repair_proposal_models import DBPreparationRepairProposal
from backend.services.preparation_operations_service import (
    get_persisted_schedule,
    list_schedule_events,
)
from backend.services.preparation_repair_proposal_read_service import (
    get_repair_proposal,
    get_repair_proposal_acceptance,
    list_repair_proposal_events,
)
from backend.services.preparation_schedule_derivation_service import (
    get_schedule_derivation_evidence,
)
from backend.services.preparation_task_execution_authoritative_service import (
    get_task_execution_overview,
)
from backend.services.preparation_task_execution_eligibility_service import (
    get_task_execution_eligibility,
)


DOCUMENT_VERSION = "preparation-schedule-support-export-v1"
AfterScheduleReadHook = Callable[[PersistedPreparationScheduleView], None]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _related_proposal_ids(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    derivation_proposal_id: int | None,
) -> list[int]:
    predicates = [DBPreparationRepairProposal.source_schedule_id == schedule_id]
    if derivation_proposal_id is not None:
        predicates.append(DBPreparationRepairProposal.id == derivation_proposal_id)
    rows = (
        db.query(DBPreparationRepairProposal.id)
        .filter(
            DBPreparationRepairProposal.household_id == household_id,
            or_(*predicates),
        )
        .order_by(DBPreparationRepairProposal.id)
        .all()
    )
    return [int(value[0]) for value in rows]


def _build_snapshot(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    database_dialect: str,
    snapshot_isolation: str,
    snapshot_marker: str | None,
    snapshot_started_at: datetime,
    after_schedule_read: Optional[AfterScheduleReadHook],
) -> PreparationScheduleSupportExport:
    schedule = get_persisted_schedule(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    if after_schedule_read is not None:
        after_schedule_read(schedule)

    schedule_events = list_schedule_events(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    derivation = get_schedule_derivation_evidence(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    eligibility = get_task_execution_eligibility(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    task_execution = get_task_execution_overview(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )

    proposal_ids = _related_proposal_ids(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        derivation_proposal_id=derivation.source_repair_proposal_id,
    )
    proposals = [
        get_repair_proposal(
            db,
            household_id=household_id,
            proposal_id=proposal_id,
        )
        for proposal_id in proposal_ids
    ]
    acceptances: list[PreparationRepairProposalAcceptanceView] = []
    proposal_events = {}
    for proposal in proposals:
        proposal_events[str(proposal.id)] = list_repair_proposal_events(
            db,
            household_id=household_id,
            proposal_id=proposal.id,
        )
        if proposal.status == PreparationRepairProposalStatus.ACCEPTED:
            acceptances.append(
                get_repair_proposal_acceptance(
                    db,
                    household_id=household_id,
                    proposal_id=proposal.id,
                )
            )

    evidence_payload = {
        "document_version": DOCUMENT_VERSION,
        "household_id": household_id,
        "schedule_id": schedule_id,
        "schedule": schedule.model_dump(mode="json"),
        "schedule_events": [
            value.model_dump(mode="json") for value in schedule_events
        ],
        "derivation": derivation.model_dump(mode="json"),
        "task_execution_eligibility": eligibility.model_dump(mode="json"),
        "task_execution": task_execution.model_dump(mode="json"),
        "related_repair_proposals": [
            value.model_dump(mode="json") for value in proposals
        ],
        "repair_acceptances": [
            value.model_dump(mode="json") for value in acceptances
        ],
        "repair_proposal_events": {
            key: [value.model_dump(mode="json") for value in values]
            for key, values in proposal_events.items()
        },
        "mutation_performed": False,
        "actual_execution_verified": False,
        "food_safety_verified": False,
    }
    snapshot_completed_at = utcnow()
    return PreparationScheduleSupportExport.model_validate(
        {
            **evidence_payload,
            "database_dialect": database_dialect,
            "snapshot_isolation": snapshot_isolation,
            "snapshot_read_only": True,
            "snapshot_marker": snapshot_marker,
            "snapshot_started_at": snapshot_started_at.isoformat(),
            "snapshot_completed_at": snapshot_completed_at.isoformat(),
            "evidence_hash": _canonical_hash(evidence_payload),
        }
    )


def preparation_schedule_support_evidence_hash(
    value: PreparationScheduleSupportExport,
) -> str:
    """Recompute the canonical evidence hash without transaction metadata."""

    payload = value.model_dump(
        mode="json",
        exclude={
            "database_dialect",
            "snapshot_isolation",
            "snapshot_read_only",
            "snapshot_marker",
            "snapshot_started_at",
            "snapshot_completed_at",
            "evidence_hash",
        },
    )
    return _canonical_hash(payload)


def export_preparation_schedule_support_snapshot(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    after_schedule_read: Optional[AfterScheduleReadHook] = None,
) -> PreparationScheduleSupportExport:
    """Return one internally consistent, non-mutating support snapshot."""

    bind = db.get_bind()
    dialect = bind.dialect.name
    started_at = utcnow()

    if dialect != "postgresql":
        return _build_snapshot(
            db,
            household_id=household_id,
            schedule_id=schedule_id,
            database_dialect=dialect,
            snapshot_isolation="serializable",
            snapshot_marker=None,
            snapshot_started_at=started_at,
            after_schedule_read=after_schedule_read,
        )

    engine = bind.engine if hasattr(bind, "engine") else bind
    connection = engine.connect().execution_options(
        isolation_level="REPEATABLE READ"
    )
    transaction = connection.begin()
    snapshot_db = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        snapshot_db.execute(text("SET TRANSACTION READ ONLY"))
        isolation = str(
            snapshot_db.execute(text("SHOW transaction_isolation")).scalar_one()
        ).strip().lower().replace(" ", "_")
        marker = str(
            snapshot_db.execute(text("SELECT txid_current_snapshot()"))
            .scalar_one()
        )
        return _build_snapshot(
            snapshot_db,
            household_id=household_id,
            schedule_id=schedule_id,
            database_dialect=dialect,
            snapshot_isolation=isolation,
            snapshot_marker=marker,
            snapshot_started_at=started_at,
            after_schedule_read=after_schedule_read,
        )
    finally:
        snapshot_db.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


__all__ = [
    "DOCUMENT_VERSION",
    "export_preparation_schedule_support_snapshot",
    "preparation_schedule_support_evidence_hash",
]
