from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import HTTPException

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_execution_aware_repair import (
    PreparationExecutionAwareRepairSnapshot,
    PreparationExecutionAwareTaskEvidence,
)
from backend.domain.preparation_execution_aware_repair_proposals import (
    PreparationExecutionAwareRepairProposalCreateRequest,
)
from backend.domain.preparation_task_execution import PreparationTaskExecutionState
from backend.services.preparation_execution_aware_repair_preflight_service import (
    preflight_execution_aware_repair_request,
)


SOURCE_HASH = "a" * 64
CANONICAL_HASH = "b" * 64
RICH_HASH = "c" * 64
CHAIN_HASH = "d" * 64


def _source_request_payload() -> dict:
    return {
        "horizon_minutes": 240,
        "granularity_minutes": 5,
        "resources": [],
        "tasks": [
            {
                "task_id": "done",
                "duration_minutes": 10,
                "earliest_start_minute": 0,
                "dependencies": [],
            },
            {
                "task_id": "active",
                "duration_minutes": 20,
                "earliest_start_minute": 10,
                "dependencies": ["done"],
            },
            {
                "task_id": "blocked",
                "duration_minutes": 15,
                "earliest_start_minute": 30,
                "dependencies": ["active"],
            },
            {
                "task_id": "free",
                "duration_minutes": 12,
                "earliest_start_minute": 30,
                "dependencies": ["done"],
            },
        ],
    }


def _snapshot() -> PreparationExecutionAwareRepairSnapshot:
    tasks = [
        PreparationExecutionAwareTaskEvidence(
            task_id="active",
            state=PreparationTaskExecutionState.IN_PROGRESS,
            planned_start_minute=10,
            planned_finish_minute=30,
            dependencies=["done"],
            latest_event_id=2,
            confirmed_start_minute=11,
            frozen=True,
            terminal=False,
            repairable=False,
        ),
        PreparationExecutionAwareTaskEvidence(
            task_id="blocked",
            state=PreparationTaskExecutionState.PLANNED,
            planned_start_minute=30,
            planned_finish_minute=45,
            dependencies=["active"],
            frozen=False,
            terminal=False,
            repairable=True,
        ),
        PreparationExecutionAwareTaskEvidence(
            task_id="done",
            state=PreparationTaskExecutionState.COMPLETED,
            planned_start_minute=0,
            planned_finish_minute=10,
            dependencies=[],
            latest_event_id=1,
            confirmed_terminal_minute=10,
            terminal_event_type="completed",
            terminal_reason="confirmed",
            frozen=True,
            terminal=True,
            repairable=False,
        ),
        PreparationExecutionAwareTaskEvidence(
            task_id="free",
            state=PreparationTaskExecutionState.PLANNED,
            planned_start_minute=30,
            planned_finish_minute=42,
            dependencies=["done"],
            frozen=False,
            terminal=False,
            repairable=True,
        ),
    ]
    return PreparationExecutionAwareRepairSnapshot(
        household_id="household-1",
        source_schedule_id=7,
        source_schedule_version=3,
        source_schedule_status="approved",
        source_schedule_hash=SOURCE_HASH,
        canonical_execution_snapshot_hash=CANONICAL_HASH,
        event_count=2,
        event_ids=[1, 2],
        first_event_schedule_version=1,
        latest_event_schedule_version=3,
        event_chain_hash=CHAIN_HASH,
        tasks=tasks,
        frozen_task_ids=["active", "done"],
        active_task_ids=["active"],
        terminal_task_ids=["done"],
        satisfied_dependency_task_ids=["done"],
        repairable_task_ids=["blocked", "free"],
        ready_repairable_task_ids=["free"],
        blocked_repairable_tasks={"blocked": ["active"]},
        snapshot_hash=RICH_HASH,
        requires_human_acceptance=True,
        repair_computation_performed=False,
        persistence_performed=False,
        limitations=["test fixture"],
    )


def _payload(revised: dict | None = None, **overrides):
    raw = {
        "source_schedule_id": 7,
        "expected_source_version": 3,
        "expected_source_schedule_hash": SOURCE_HASH,
        "expected_execution_snapshot_hash": CANONICAL_HASH,
        "expected_execution_aware_snapshot_hash": RICH_HASH,
        "target_calendar_version_id": 9,
        "revised_request": revised or _source_request_payload(),
        "acknowledge_execution_history_immutable": True,
        "acknowledge_in_progress_work_not_moved": True,
        "acknowledge_preflight_only": True,
        "idempotency_key": "execution-aware-preflight-1",
    }
    raw.update(overrides)
    return PreparationExecutionAwareRepairProposalCreateRequest.model_validate(raw)


def test_preflight_normalizes_terminal_dependencies_and_blocks_active_descendants():
    revised = _source_request_payload()
    for task in revised["tasks"]:
        if task["task_id"] == "free":
            task["duration_minutes"] = 18
        if task["task_id"] == "blocked":
            task["duration_minutes"] = 22

    result = preflight_execution_aware_repair_request(
        snapshot=_snapshot(),
        source_request=PreparationScheduleRequest.model_validate(_source_request_payload()),
        payload=_payload(revised),
    )

    assert result.frozen_task_ids == ["active", "done"]
    assert result.blocked_by_in_progress_task_ids == {"blocked": ["active"]}
    assert result.candidate_task_ids == ["free"]
    assert result.ready_for_proposal_computation is True
    assert [task.task_id for task in result.normalized_future_request.tasks] == ["free"]
    assert result.normalized_future_request.tasks[0].dependencies == []
    assert result.normalized_future_request.tasks[0].duration_minutes == 18
    assert result.repair_computation_performed is False
    assert result.proposal_persistence_performed is False
    assert result.schedule_persistence_performed is False


def test_preflight_rejects_frozen_task_mutation():
    revised = deepcopy(_source_request_payload())
    for task in revised["tasks"]:
        if task["task_id"] == "active":
            task["duration_minutes"] = 21

    with pytest.raises(HTTPException) as exc_info:
        preflight_execution_aware_repair_request(
            snapshot=_snapshot(),
            source_request=PreparationScheduleRequest.model_validate(_source_request_payload()),
            payload=_payload(revised),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "execution_aware_repair_frozen_task_changed"
    assert exc_info.value.detail["task_id"] == "active"


def test_preflight_rejects_stale_canonical_snapshot_hash():
    with pytest.raises(HTTPException) as exc_info:
        preflight_execution_aware_repair_request(
            snapshot=_snapshot(),
            source_request=PreparationScheduleRequest.model_validate(_source_request_payload()),
            payload=_payload(expected_execution_snapshot_hash="e" * 64),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "execution_aware_repair_snapshot_changed"
    assert exc_info.value.detail["field"] == "execution_snapshot_hash"


def test_preflight_rejects_task_addition_or_removal_until_provenance_exists():
    revised = deepcopy(_source_request_payload())
    revised["tasks"] = [task for task in revised["tasks"] if task["task_id"] != "free"]

    with pytest.raises(HTTPException) as exc_info:
        preflight_execution_aware_repair_request(
            snapshot=_snapshot(),
            source_request=PreparationScheduleRequest.model_validate(_source_request_payload()),
            payload=_payload(revised),
        )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail["code"]
        == "execution_aware_repair_task_identity_change_not_enabled"
    )
    assert exc_info.value.detail["removed_task_ids"] == ["free"]
