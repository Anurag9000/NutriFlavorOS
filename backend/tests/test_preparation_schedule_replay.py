from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair import PreparationScheduleRepairRequest
from backend.domain.preparation_schedule_replay import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
    OriginalPreparationScheduleReplay,
    PreparationScheduleDerivationMethod,
    RepairedPreparationScheduleReplay,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.engines.prep_schedule_repair import repair_preparation_schedule
from backend.services.preparation_schedule_replay_service import (
    PreparationScheduleReplayError,
    canonical_hash,
    replay_preparation_schedule,
)


def request(*, capacity: int = 1) -> PreparationScheduleRequest:
    return PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 120,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "person",
                    "label": "Available cook",
                    "capacity": capacity,
                    "availability_windows": [
                        {"start_minute": 0, "end_minute": 120}
                    ],
                }
            ],
            "tasks": [
                {
                    "task_id": "task.a",
                    "duration_minutes": 10,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 60,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {"label": "A"},
                },
                {
                    "task_id": "task.b",
                    "duration_minutes": 10,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 60,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {"label": "B"},
                },
            ],
        }
    )


def original_envelope() -> OriginalPreparationScheduleReplay:
    value = request()
    response = build_preparation_schedule(value)
    return OriginalPreparationScheduleReplay(
        request=value,
        expected_response=response,
        expected_request_hash=canonical_hash(value.model_dump(mode="json")),
        expected_response_hash=canonical_hash(response.model_dump(mode="json")),
    )


def repair_envelope() -> RepairedPreparationScheduleReplay:
    previous = request(capacity=2)
    revised = request(capacity=1)
    previous_response = build_preparation_schedule(previous)
    repair_request = PreparationScheduleRepairRequest(
        previous_request=previous,
        previous_response=previous_response,
        revised_request=revised,
        immutable_task_ids=[],
        allow_partial=False,
    )
    result = repair_preparation_schedule(repair_request)
    return RepairedPreparationScheduleReplay(
        repair_request=repair_request,
        expected_result=result,
        expected_repair_request_hash=canonical_hash(
            repair_request.model_dump(mode="json")
        ),
        expected_repair_result_hash=canonical_hash(
            result.model_dump(mode="json")
        ),
        expected_revised_request_hash=result.revised_request_hash,
        expected_response_hash=result.repaired_response_hash,
    )


def test_original_scheduler_replay_is_hash_exact_and_deterministic():
    envelope = original_envelope()

    evidence = replay_preparation_schedule(
        method=PreparationScheduleDerivationMethod.ORIGINAL,
        original=envelope,
    )

    assert evidence.method == PreparationScheduleDerivationMethod.ORIGINAL
    assert evidence.deterministic is True
    assert evidence.request_hash == envelope.expected_request_hash
    assert evidence.response_hash == envelope.expected_response_hash
    assert evidence.result_hash is None
    assert evidence.replayed_response.method == ORIGINAL_SCHEDULER_METHOD
    assert (
        evidence.replayed_response.model_dump(mode="json")
        == envelope.expected_response.model_dump(mode="json")
    )


def test_repair_replay_is_hash_exact_and_preserves_advisory_result():
    envelope = repair_envelope()

    evidence = replay_preparation_schedule(
        method=PreparationScheduleDerivationMethod.REPAIR,
        repair=envelope,
    )

    assert evidence.method == PreparationScheduleDerivationMethod.REPAIR
    assert evidence.deterministic is True
    assert evidence.request_hash == envelope.expected_repair_request_hash
    assert evidence.response_hash == envelope.expected_response_hash
    assert evidence.result_hash == envelope.expected_repair_result_hash
    assert evidence.replayed_response.method == REPAIR_SCHEDULER_METHOD
    assert evidence.replayed_response.unscheduled == []
    assert envelope.expected_result.accepted is False
    assert envelope.expected_result.persistence_performed is False


def test_dispatch_rejects_unknown_method_and_mixed_envelopes():
    original = original_envelope()
    repair = repair_envelope()

    with pytest.raises(PreparationScheduleReplayError) as unknown:
        replay_preparation_schedule(method="unknown-v1", original=original)
    assert unknown.value.code == "unknown_schedule_derivation_method"

    with pytest.raises(PreparationScheduleReplayError) as mixed:
        replay_preparation_schedule(
            method=PreparationScheduleDerivationMethod.ORIGINAL,
            original=original,
            repair=repair,
        )
    assert mixed.value.code == "original_replay_envelope_required"

    with pytest.raises(PreparationScheduleReplayError) as missing:
        replay_preparation_schedule(
            method=PreparationScheduleDerivationMethod.REPAIR,
            original=original,
        )
    assert missing.value.code == "repair_replay_envelope_required"


def test_original_replay_rejects_request_and_response_hash_drift():
    envelope = original_envelope()
    wrong_request = envelope.model_copy(
        update={"expected_request_hash": "0" * 64}
    )
    with pytest.raises(PreparationScheduleReplayError) as request_error:
        replay_preparation_schedule(
            method=PreparationScheduleDerivationMethod.ORIGINAL,
            original=wrong_request,
        )
    assert request_error.value.code == "original_replay_request_hash_mismatch"

    wrong_response = envelope.model_copy(
        update={"expected_response_hash": "0" * 64}
    )
    with pytest.raises(PreparationScheduleReplayError) as response_error:
        replay_preparation_schedule(
            method=PreparationScheduleDerivationMethod.ORIGINAL,
            original=wrong_response,
        )
    assert response_error.value.code == "original_replay_response_hash_mismatch"


def test_repair_replay_rejects_request_result_and_response_hash_drift():
    envelope = repair_envelope()
    fields = [
        ("expected_repair_request_hash", "repair_replay_request_hash_mismatch"),
        ("expected_repair_result_hash", "repair_replay_result_hash_mismatch"),
        (
            "expected_revised_request_hash",
            "repair_replay_revised_request_hash_mismatch",
        ),
        ("expected_response_hash", "repair_replay_stored_response_hash_mismatch"),
    ]
    for field, code in fields:
        drifted = envelope.model_copy(update={field: "0" * 64})
        with pytest.raises(PreparationScheduleReplayError) as exc:
            replay_preparation_schedule(
                method=PreparationScheduleDerivationMethod.REPAIR,
                repair=drifted,
            )
        assert exc.value.code == code


def test_repair_envelope_rejects_wrong_method_or_preaccepted_result():
    envelope = repair_envelope()
    wrong_method_payload = envelope.model_dump(mode="json")
    wrong_method_payload["expected_result"]["response"]["method"] = (
        ORIGINAL_SCHEDULER_METHOD
    )
    with pytest.raises(ValidationError):
        RepairedPreparationScheduleReplay.model_validate(wrong_method_payload)

    preaccepted_payload = envelope.model_dump(mode="json")
    preaccepted_payload["expected_result"]["accepted"] = True
    with pytest.raises(ValidationError):
        RepairedPreparationScheduleReplay.model_validate(preaccepted_payload)


def test_repair_replay_detects_tampered_stored_result_even_with_valid_model():
    envelope = repair_envelope()
    payload = envelope.expected_result.model_dump(mode="json")
    payload["warnings"] = [*payload["warnings"], "tampered warning"]
    tampered = envelope.expected_result.model_validate(payload)
    drifted = envelope.model_copy(update={"expected_result": tampered})

    with pytest.raises(PreparationScheduleReplayError) as exc:
        replay_preparation_schedule(
            method=PreparationScheduleDerivationMethod.REPAIR,
            repair=drifted,
        )
    assert exc.value.code == "repair_replay_result_hash_mismatch"
