"""Authorization-preserving preparation support snapshot boundary.

The HTTP request session performs the normal non-disclosing access check. This
service repeats that check inside the exact database snapshot used to assemble
the export, closing the membership-change gap between request authorization and
the dedicated PostgreSQL evidence transaction.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.domain.household_access import HouseholdRole
from backend.domain.preparation_operations import PersistedPreparationScheduleView
from backend.domain.preparation_schedule_support_export import (
    PreparationScheduleSupportExport,
)
from backend.services.household_access_service import require_household_access
from backend.services.preparation_schedule_support_export_service import (
    AfterScheduleReadHook,
    _build_snapshot,
    utcnow,
)


def export_authorized_preparation_schedule_support_snapshot(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    authorized_user_id: str,
    after_schedule_read: Optional[AfterScheduleReadHook] = None,
) -> PreparationScheduleSupportExport:
    """Revalidate viewer access in the exact exported database snapshot."""

    bind = db.get_bind()
    dialect = bind.dialect.name
    started_at = utcnow()

    if dialect != "postgresql":
        require_household_access(
            db,
            household_id,
            authorized_user_id,
            HouseholdRole.VIEWER,
        )
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
        require_household_access(
            snapshot_db,
            household_id,
            authorized_user_id,
            HouseholdRole.VIEWER,
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


__all__ = ["export_authorized_preparation_schedule_support_snapshot"]
