"""Compatibility entry point for authoritative schedule completion."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.domain.preparation_operations import (
    PersistedPreparationScheduleView,
    PreparationScheduleEventType,
    ScheduleStateTransitionRequest,
)
from backend.services.preparation_operations_service import transition_schedule


def complete_schedule_with_execution_guard(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    payload: ScheduleStateTransitionRequest,
) -> PersistedPreparationScheduleView:
    """Delegate completion to the lowest authoritative transition layer.

    ``transition_schedule`` now owns task terminality, lifecycle validity,
    optimistic versions, idempotency, locking, event append, and commit
    semantics. Keeping this named entry point preserves the API/service surface
    without maintaining a second completion proof.
    """

    return transition_schedule(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        actor_user_id=actor_user_id,
        event_type=PreparationScheduleEventType.COMPLETED,
        payload=payload,
    )
