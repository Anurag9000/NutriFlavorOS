"""Authoritative household preparation calendar and schedule services.

The implementation remains in ``preparation_operations_service_impl`` so its
established public and private helpers stay byte-for-byte preserved. This
facade re-exports that surface and strengthens the lowest exported schedule
transition: every new ``completed`` transition must prove that all
 deterministic tasks are explicitly completed or skipped.
"""

from __future__ import annotations

from backend.services import preparation_operations_service_impl as _impl


# Preserve every established import, including private helpers used by the
# tightly coupled transactional services. The authoritative transition below
# intentionally overrides the implementation module's compatibility function.
for _exported_name in dir(_impl):
    if not _exported_name.startswith("__"):
        globals()[_exported_name] = getattr(_impl, _exported_name)

_original_transition_schedule = _impl.transition_schedule


def _assert_completion_authority(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    event_type: PreparationScheduleEventType,
    payload: ScheduleStateTransitionRequest,
) -> None:
    """Enforce terminal task evidence without changing legacy error precedence.

    Exact idempotent retries, contradictory key reuse, missing schedules,
    optimistic-version conflicts, and invalid lifecycle transitions remain the
    implementation service's responsibility. Terminality is checked only for a
    valid new ``approved -> completed`` request while the household and schedule
    rows are locked in the same transaction.
    """

    if event_type != PreparationScheduleEventType.COMPLETED:
        return

    _impl._lock_household(db, household_id)
    fingerprint = _impl._transition_fingerprint(
        schedule_id,
        event_type,
        payload,
        actor_user_id,
    )
    existing_event = (
        db.query(_impl.DBPreparationScheduleEvent)
        .filter(
            _impl.DBPreparationScheduleEvent.household_id == household_id,
            _impl.DBPreparationScheduleEvent.idempotency_key
            == payload.idempotency_key,
        )
        .with_for_update()
        .first()
    )
    if existing_event is not None:
        # Delegate exact-retry or contradictory-key handling unchanged.
        return

    schedule = (
        db.query(_impl.DBPersistedPreparationSchedule)
        .filter(
            _impl.DBPersistedPreparationSchedule.id == schedule_id,
            _impl.DBPersistedPreparationSchedule.household_id == household_id,
        )
        .with_for_update()
        .first()
    )
    if schedule is None:
        return
    if schedule.version != payload.expected_version:
        return
    if schedule.status != PreparationScheduleStatus.APPROVED.value:
        return

    # Local import avoids the established execution-service -> operations-service
    # dependency cycle during module initialization.
    from backend.services.preparation_task_execution_service import (
        assert_schedule_tasks_terminal,
    )

    assert_schedule_tasks_terminal(db, schedule=schedule)


def transition_schedule(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
    actor_user_id: str,
    event_type: PreparationScheduleEventType,
    payload: ScheduleStateTransitionRequest,
) -> PersistedPreparationScheduleView:
    """Apply one authoritative lifecycle transition.

    Schedule completion cannot bypass explicit task terminality even when a
    service caller invokes this lowest transition directly.
    """

    _assert_completion_authority(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload=payload,
    )
    return _original_transition_schedule(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload=payload,
    )


__all__ = list(
    getattr(
        _impl,
        "__all__",
        [name for name in dir(_impl) if not name.startswith("_")],
    )
)
if "transition_schedule" not in __all__:
    __all__.append("transition_schedule")
