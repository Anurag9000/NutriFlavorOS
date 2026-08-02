from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
)


BASE_PAYLOAD = {
    "expected_proposal_version": 1,
    "expected_source_schedule_version": 1,
    "expected_source_schedule_hash": "a" * 64,
    "expected_source_schedule_request_hash": "b" * 64,
    "expected_target_calendar_content_hash": "c" * 64,
    "expected_repair_request_hash": "d" * 64,
    "expected_repair_result_hash": "e" * 64,
    "expected_revised_request_hash": "f" * 64,
    "expected_repaired_response_hash": "0" * 64,
    "acknowledged_task_ids": [],
    "reason": "Create a separately approvable repaired draft",
    "acknowledge_creates_new_draft_only": True,
}


def test_acceptance_key_at_safe_maximum_is_valid():
    value = PreparationRepairProposalAcceptRequest.model_validate(
        {
            **BASE_PAYLOAD,
            "idempotency_key": "a" * 160,
        }
    )

    assert len(value.idempotency_key) == 160


def test_acceptance_key_above_safe_maximum_is_rejected():
    with pytest.raises(ValidationError) as exc:
        PreparationRepairProposalAcceptRequest.model_validate(
            {
                **BASE_PAYLOAD,
                "idempotency_key": "a" * 161,
            }
        )

    assert any(
        tuple(error["loc"]) == ("idempotency_key",)
        and error["type"] == "string_too_long"
        for error in exc.value.errors()
    )
