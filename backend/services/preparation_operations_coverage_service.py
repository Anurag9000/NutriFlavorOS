"""Descriptive provenance coverage for household preparation operations."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.domain.preparation_operations import (
    CalendarEvidenceStatus,
    PreparationScheduleStatus,
)
from backend.domain.preparation_operations_coverage import (
    PreparationOperationsCoverageView,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
    DBResourceCalendarVersion,
)
from backend.services.preparation_operations_service import utcnow


REPLAY_STATUSES = (
    "replayable",
    "legacy_request_missing",
    "legacy_occurrence_set_missing",
)


def _coverage(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def get_preparation_operations_coverage(
    db: Session,
    *,
    household_id: str,
) -> PreparationOperationsCoverageView:
    """Summarize stored provenance without replaying or certifying schedules."""

    calendars = (
        db.query(DBResourceCalendarVersion)
        .filter(DBResourceCalendarVersion.household_id == household_id)
        .order_by(
            DBResourceCalendarVersion.created_at.desc(),
            DBResourceCalendarVersion.id.desc(),
        )
        .all()
    )
    schedules = (
        db.query(DBPersistedPreparationSchedule)
        .filter(DBPersistedPreparationSchedule.household_id == household_id)
        .order_by(
            DBPersistedPreparationSchedule.created_at.desc(),
            DBPersistedPreparationSchedule.id.desc(),
        )
        .all()
    )
    event_total = int(
        db.query(func.count(DBPreparationScheduleEvent.id))
        .filter(DBPreparationScheduleEvent.household_id == household_id)
        .scalar()
        or 0
    )

    calendar_total = len(calendars)
    reviewed_calendar_total = sum(
        value.evidence_status == CalendarEvidenceStatus.REVIEWED.value
        for value in calendars
    )
    active_reviewed_calendar_count = sum(
        bool(value.active)
        and value.evidence_status == CalendarEvidenceStatus.REVIEWED.value
        for value in calendars
    )

    schedule_total = len(schedules)
    status_counts = Counter(value.status for value in schedules)
    schedule_status_counts = {
        status.value: int(status_counts.get(status.value, 0))
        for status in PreparationScheduleStatus
    }

    replay_counts = Counter()
    occurrence_document_count = 0
    scheduler_request_count = 0
    replayable_draft_count = 0
    source_plan_linked_count = 0
    for value in schedules:
        has_occurrence = value.occurrence_set_payload is not None
        has_request = (
            value.schedule_request_payload is not None
            and bool(value.schedule_request_hash)
        )
        occurrence_document_count += int(has_occurrence)
        scheduler_request_count += int(has_request)
        source_plan_linked_count += int(
            value.source_plan_id is not None
            and value.source_plan_version is not None
        )
        if not has_request:
            replay_status = "legacy_request_missing"
        elif not has_occurrence:
            replay_status = "legacy_occurrence_set_missing"
        else:
            replay_status = "replayable"
            if value.status == PreparationScheduleStatus.DRAFT.value:
                replayable_draft_count += 1
        replay_counts[replay_status] += 1

    replay_status_counts = {
        status: int(replay_counts.get(status, 0)) for status in REPLAY_STATUSES
    }
    replayable_schedule_count = replay_status_counts["replayable"]

    warnings: list[str] = []
    if active_reviewed_calendar_count == 0:
        warnings.append("No active reviewed resource calendar is available")
    elif active_reviewed_calendar_count > 1:
        warnings.append(
            "More than one active reviewed resource calendar was observed"
        )
    if schedule_total == 0:
        warnings.append("No persisted preparation schedules are available")
    if replayable_schedule_count < schedule_total:
        warnings.append(
            "One or more legacy schedules lack complete replay provenance"
        )
    if source_plan_linked_count < schedule_total and schedule_total:
        warnings.append(
            "One or more schedules are not linked to a source plan version"
        )

    return PreparationOperationsCoverageView(
        household_id=household_id,
        generated_at=utcnow().isoformat(),
        calendar_total=calendar_total,
        reviewed_calendar_total=reviewed_calendar_total,
        active_reviewed_calendar_count=active_reviewed_calendar_count,
        schedule_total=schedule_total,
        schedule_status_counts=schedule_status_counts,
        replay_status_counts=replay_status_counts,
        occurrence_document_count=occurrence_document_count,
        scheduler_request_count=scheduler_request_count,
        replayable_schedule_count=replayable_schedule_count,
        replayable_draft_count=replayable_draft_count,
        source_plan_linked_count=source_plan_linked_count,
        event_total=event_total,
        occurrence_document_coverage=_coverage(
            occurrence_document_count,
            schedule_total,
        ),
        scheduler_request_coverage=_coverage(
            scheduler_request_count,
            schedule_total,
        ),
        replayable_schedule_coverage=_coverage(
            replayable_schedule_count,
            schedule_total,
        ),
        latest_calendar_created_at=(
            calendars[0].created_at.isoformat() if calendars else None
        ),
        latest_schedule_created_at=(
            schedules[0].created_at.isoformat() if schedules else None
        ),
        warnings=warnings,
    )
