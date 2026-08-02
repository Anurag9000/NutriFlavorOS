from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_authoritative_coverage_history_fixture(request, monkeypatch):
    """Keep the partial-history coverage test on one active calendar.

    This narrowly patches only the dedicated authoritative coverage test module.
    It tolerates both the original two-helper form and the corrected explicit
    same-calendar helper form without changing any production behavior.
    """

    module = request.module
    if not module.__name__.endswith(
        "test_preparation_operations_coverage_authoritative_entry"
    ):
        return
    original = getattr(module, "_approved_schedule", None)
    if original is None:
        return

    def same_calendar_schedule(db, suffix: str = "primary"):
        if suffix != "history-second":
            value = original(db, suffix)
            if suffix == "history-first":
                db.info["authoritative_coverage_first_schedule"] = value
            return value
        first = db.info.get("authoritative_coverage_first_schedule")
        if first is None:
            return original(db, suffix)
        from backend.domain.preparation_operations import PreparationScheduleEventType
        from backend.services.preparation_operations_service import (
            create_persisted_schedule,
            transition_schedule,
        )
        from backend.tests.test_preparation_operations_service import (
            persisted_payload,
            transition_payload,
        )

        draft = create_persisted_schedule(
            db,
            household_id=module.HOUSEHOLD_ID,
            actor_user_id=module.OWNER_ID,
            payload=persisted_payload(
                type("Calendar", (), {"id": first.calendar_version_id})(),
                "coverage-history-second-schedule",
                household_id=module.HOUSEHOLD_ID,
            ),
        )
        return transition_schedule(
            db,
            household_id=module.HOUSEHOLD_ID,
            schedule_id=draft.id,
            actor_user_id=module.OWNER_ID,
            event_type=PreparationScheduleEventType.APPROVED,
            payload=transition_payload(
                draft.version,
                "coverage-history-second-approve",
                "Approve second schedule on the same active calendar",
            ),
        )

    monkeypatch.setattr(module, "_approved_schedule", same_calendar_schedule)
