"""Side-effect-free deterministic replay for persisted preparation schedules.

The service never reads or writes a database. Callers must provide a complete,
method-specific evidence envelope. Unknown methods, hash drift, non-determinism,
incomplete output, or response drift fail closed with stable error codes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from backend.domain.preparation_schedule_replay import (
    ORIGINAL_SCHEDULER_METHOD,
    REPAIR_SCHEDULER_METHOD,
    OriginalPreparationScheduleReplay,
    PreparationScheduleDerivationMethod,
    PreparationScheduleReplayEvidence,
    RepairedPreparationScheduleReplay,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.engines.prep_schedule_repair import (
    PreparationRepairError,
    repair_preparation_schedule,
)


class PreparationScheduleReplayError(ValueError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


def canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def replay_original_schedule(
    envelope: OriginalPreparationScheduleReplay,
) -> PreparationScheduleReplayEvidence:
    request_payload = envelope.request.model_dump(mode="json")
    expected_payload = envelope.expected_response.model_dump(mode="json")
    request_hash = canonical_hash(request_payload)
    expected_hash = canonical_hash(expected_payload)
    if request_hash != envelope.expected_request_hash:
        raise PreparationScheduleReplayError(
            code="original_replay_request_hash_mismatch",
            message="Original scheduler request differs from its expected hash",
            details={
                "expected_hash": envelope.expected_request_hash,
                "observed_hash": request_hash,
            },
        )
    if expected_hash != envelope.expected_response_hash:
        raise PreparationScheduleReplayError(
            code="original_replay_response_hash_mismatch",
            message="Stored original response differs from its expected hash",
            details={
                "expected_hash": envelope.expected_response_hash,
                "observed_hash": expected_hash,
            },
        )

    replay = build_preparation_schedule(envelope.request)
    replay_payload = replay.model_dump(mode="json")
    replay_hash = canonical_hash(replay_payload)
    if replay.method != ORIGINAL_SCHEDULER_METHOD or not replay.deterministic:
        raise PreparationScheduleReplayError(
            code="original_replay_method_mismatch",
            message="Original scheduler replay returned an unexpected method",
            details={
                "expected_method": ORIGINAL_SCHEDULER_METHOD,
                "observed_method": replay.method,
                "deterministic": replay.deterministic,
            },
        )
    if replay.unscheduled:
        raise PreparationScheduleReplayError(
            code="original_replay_incomplete",
            message="Original scheduler replay contains unresolved tasks",
            details={
                "task_ids": sorted(value.task_id for value in replay.unscheduled),
            },
        )
    if replay_payload != expected_payload or replay_hash != envelope.expected_response_hash:
        raise PreparationScheduleReplayError(
            code="original_replay_output_mismatch",
            message="Original scheduler replay differs from the stored response",
            details={
                "expected_hash": envelope.expected_response_hash,
                "observed_hash": replay_hash,
            },
        )
    return PreparationScheduleReplayEvidence(
        method=PreparationScheduleDerivationMethod.ORIGINAL,
        deterministic=True,
        request_hash=request_hash,
        response_hash=replay_hash,
        result_hash=None,
        replayed_response=replay,
    )


def replay_repaired_schedule(
    envelope: RepairedPreparationScheduleReplay,
) -> PreparationScheduleReplayEvidence:
    request_payload = envelope.repair_request.model_dump(mode="json")
    expected_result_payload = envelope.expected_result.model_dump(mode="json")
    request_hash = canonical_hash(request_payload)
    expected_result_hash = canonical_hash(expected_result_payload)
    revised_request_hash = canonical_hash(
        envelope.repair_request.revised_request.model_dump(mode="json")
    )
    expected_response_hash = canonical_hash(
        envelope.expected_result.response.model_dump(mode="json")
    )
    if request_hash != envelope.expected_repair_request_hash:
        raise PreparationScheduleReplayError(
            code="repair_replay_request_hash_mismatch",
            message="Repair request differs from its expected hash",
            details={
                "expected_hash": envelope.expected_repair_request_hash,
                "observed_hash": request_hash,
            },
        )
    if expected_result_hash != envelope.expected_repair_result_hash:
        raise PreparationScheduleReplayError(
            code="repair_replay_result_hash_mismatch",
            message="Stored repair result differs from its expected hash",
            details={
                "expected_hash": envelope.expected_repair_result_hash,
                "observed_hash": expected_result_hash,
            },
        )
    if revised_request_hash != envelope.expected_revised_request_hash:
        raise PreparationScheduleReplayError(
            code="repair_replay_revised_request_hash_mismatch",
            message="Revised scheduler request differs from its expected hash",
            details={
                "expected_hash": envelope.expected_revised_request_hash,
                "observed_hash": revised_request_hash,
            },
        )
    if expected_response_hash != envelope.expected_response_hash:
        raise PreparationScheduleReplayError(
            code="repair_replay_stored_response_hash_mismatch",
            message="Stored repaired response differs from its expected hash",
            details={
                "expected_hash": envelope.expected_response_hash,
                "observed_hash": expected_response_hash,
            },
        )

    try:
        replay = repair_preparation_schedule(envelope.repair_request)
    except PreparationRepairError as exc:
        raise PreparationScheduleReplayError(
            code="repair_replay_computation_failed",
            message="Deterministic repair replay failed",
            details=exc.as_dict(),
        ) from exc

    replay_payload = replay.model_dump(mode="json")
    replay_result_hash = canonical_hash(replay_payload)
    replay_response_hash = canonical_hash(replay.response.model_dump(mode="json"))
    if replay.response.method != REPAIR_SCHEDULER_METHOD or not replay.response.deterministic:
        raise PreparationScheduleReplayError(
            code="repair_replay_method_mismatch",
            message="Repair replay returned an unexpected derivation method",
            details={
                "expected_method": REPAIR_SCHEDULER_METHOD,
                "observed_method": replay.response.method,
                "deterministic": replay.response.deterministic,
            },
        )
    if not replay.complete or replay.unscheduled_task_ids or replay.response.unscheduled:
        raise PreparationScheduleReplayError(
            code="repair_replay_incomplete",
            message="Repair replay contains unresolved tasks",
            details={
                "task_ids": sorted(replay.unscheduled_task_ids),
            },
        )
    if replay_payload != expected_result_payload:
        raise PreparationScheduleReplayError(
            code="repair_replay_output_mismatch",
            message="Repair replay differs from the stored repair result",
            details={
                "expected_hash": envelope.expected_repair_result_hash,
                "observed_hash": replay_result_hash,
            },
        )
    if replay_result_hash != envelope.expected_repair_result_hash:
        raise PreparationScheduleReplayError(
            code="repair_replay_result_hash_drift",
            message="Repair replay result hash differs from expected evidence",
            details={
                "expected_hash": envelope.expected_repair_result_hash,
                "observed_hash": replay_result_hash,
            },
        )
    if replay.revised_request_hash != envelope.expected_revised_request_hash:
        raise PreparationScheduleReplayError(
            code="repair_replay_internal_request_hash_drift",
            message="Repair replay emitted a different revised-request hash",
            details={
                "expected_hash": envelope.expected_revised_request_hash,
                "observed_hash": replay.revised_request_hash,
            },
        )
    if (
        replay.repaired_response_hash != envelope.expected_response_hash
        or replay_response_hash != envelope.expected_response_hash
    ):
        raise PreparationScheduleReplayError(
            code="repair_replay_response_hash_drift",
            message="Repair replay emitted a different response hash",
            details={
                "expected_hash": envelope.expected_response_hash,
                "reported_hash": replay.repaired_response_hash,
                "observed_hash": replay_response_hash,
            },
        )
    return PreparationScheduleReplayEvidence(
        method=PreparationScheduleDerivationMethod.REPAIR,
        deterministic=True,
        request_hash=request_hash,
        response_hash=replay_response_hash,
        result_hash=replay_result_hash,
        replayed_response=replay.response,
    )


def replay_preparation_schedule(
    *,
    method: PreparationScheduleDerivationMethod | str,
    original: OriginalPreparationScheduleReplay | None = None,
    repair: RepairedPreparationScheduleReplay | None = None,
) -> PreparationScheduleReplayEvidence:
    try:
        selected = PreparationScheduleDerivationMethod(method)
    except ValueError as exc:
        raise PreparationScheduleReplayError(
            code="unknown_schedule_derivation_method",
            message="Schedule derivation method is not supported",
            details={"method": str(method)},
        ) from exc

    if selected is PreparationScheduleDerivationMethod.ORIGINAL:
        if original is None or repair is not None:
            raise PreparationScheduleReplayError(
                code="original_replay_envelope_required",
                message="Original replay requires only an original evidence envelope",
            )
        return replay_original_schedule(original)
    if repair is None or original is not None:
        raise PreparationScheduleReplayError(
            code="repair_replay_envelope_required",
            message="Repair replay requires only a repair evidence envelope",
        )
    return replay_repaired_schedule(repair)


__all__ = [
    "PreparationScheduleReplayError",
    "canonical_hash",
    "replay_original_schedule",
    "replay_preparation_schedule",
    "replay_repaired_schedule",
]
