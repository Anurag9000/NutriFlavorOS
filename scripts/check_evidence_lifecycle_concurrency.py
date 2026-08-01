#!/usr/bin/env python3
"""PostgreSQL concurrency probe for immutable evidence lifecycle operations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from typing import Callable

from backend.database import SessionLocal
from backend.domain.evidence_history import (
    EvidenceRecordStatus,
    IngredientConversionVersionInput,
    StoragePolicyVersionInput,
)
from backend.domain.evidence_lifecycle import (
    EvidenceLifecycleAction,
    EvidenceLifecycleBatchDocument,
    EvidenceLifecycleRequest,
    EvidenceTargetKind,
)
from backend.evidence_history_models import (
    DBEvidenceLifecycleEvent,
    DBIngredientConversionVersion,
    DBStoragePolicyVersion,
)
from backend.services.evidence_history_service import (
    register_conversion_version,
    register_storage_policy_version,
)
from backend.services.evidence_lifecycle_service import (
    apply_evidence_lifecycle_batch,
)


CONVERSION_NAME = "ci lifecycle concurrency ingredient"
POLICY_KEY = "ci_lifecycle_concurrency_policy"


def _conversion(version: str, multiplier: float = 100.0):
    return IngredientConversionVersionInput(
        canonical_name=CONVERSION_NAME,
        from_unit="cup",
        to_unit="g",
        record_version=version,
        multiplier_min=multiplier,
        multiplier_max=multiplier,
        source_name="Lifecycle concurrency fixture",
        source_url=f"https://example.test/lifecycle/conversion/{version}",
        source_version=version,
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        reviewed_by="CI lifecycle probe",
        active=True,
    )


def _policy(version: str, hours: float = 24.0):
    return StoragePolicyVersionInput(
        policy_key=POLICY_KEY,
        policy_version=version,
        food_category="CI lifecycle fixture",
        storage_state="refrigerated",
        duration_min_hours=hours,
        duration_max_hours=hours,
        maximum_temperature_c=4,
        source_name="Lifecycle concurrency fixture",
        source_url=f"https://example.test/lifecycle/policy/{version}",
        source_version=version,
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        reviewed_by="CI lifecycle probe",
        safety_scope="test_only",
        active=True,
    )


def _action(
    target_kind: EvidenceTargetKind,
    target_id: int,
    idempotency_key: str,
    *,
    action: EvidenceLifecycleAction = EvidenceLifecycleAction.DEACTIVATED,
):
    return EvidenceLifecycleBatchDocument(
        actions=[
            EvidenceLifecycleRequest(
                target_kind=target_kind,
                target_id=target_id,
                action=action,
                actor="CI lifecycle probe",
                reason="Concurrent lifecycle fixture",
                idempotency_key=idempotency_key,
                metadata={"probe": "postgresql"},
            )
        ]
    )


def _run_pair(left: Callable[[], object], right: Callable[[], object]):
    barrier = Barrier(2)

    def execute(label: str, callback: Callable[[], object]):
        barrier.wait(timeout=10)
        try:
            return label, callback()
        except Exception as exc:
            return label, exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(execute, "left", left),
            pool.submit(execute, "right", right),
        ]
        return [future.result(timeout=30) for future in futures]


def _register_conversion(payload):
    with SessionLocal() as db:
        return register_conversion_version(db, payload)


def _register_policy(payload):
    with SessionLocal() as db:
        return register_storage_policy_version(db, payload)


def _apply(document):
    with SessionLocal() as db:
        return apply_evidence_lifecycle_batch(db, document)


def _reset() -> None:
    with SessionLocal() as db:
        conversion_ids = [
            value[0]
            for value in db.query(DBIngredientConversionVersion.id)
            .filter(DBIngredientConversionVersion.canonical_name == CONVERSION_NAME)
            .all()
        ]
        policy_ids = [
            value[0]
            for value in db.query(DBStoragePolicyVersion.id)
            .filter(DBStoragePolicyVersion.policy_key == POLICY_KEY)
            .all()
        ]
        if conversion_ids:
            db.query(DBEvidenceLifecycleEvent).filter(
                DBEvidenceLifecycleEvent.conversion_version_id.in_(conversion_ids)
            ).delete(synchronize_session=False)
        if policy_ids:
            db.query(DBEvidenceLifecycleEvent).filter(
                DBEvidenceLifecycleEvent.storage_policy_version_id.in_(policy_ids)
            ).delete(synchronize_session=False)
        db.query(DBIngredientConversionVersion).filter(
            DBIngredientConversionVersion.canonical_name == CONVERSION_NAME
        ).delete(synchronize_session=False)
        db.query(DBStoragePolicyVersion).filter(
            DBStoragePolicyVersion.policy_key == POLICY_KEY
        ).delete(synchronize_session=False)
        db.commit()


def _assert_identical_lifecycle_retry_collapses() -> None:
    baseline = _register_conversion(_conversion("identical-baseline"))
    document = _action(
        EvidenceTargetKind.CONVERSION,
        baseline.id,
        "ci-lifecycle-identical-retry",
    )
    results = _run_pair(lambda: _apply(document), lambda: _apply(document))
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    event_ids = {
        value.events[0].id
        for _, value in results
    }
    assert len(event_ids) == 1
    with SessionLocal() as db:
        assert db.get(DBIngredientConversionVersion, baseline.id).active is False
        rows = (
            db.query(DBEvidenceLifecycleEvent)
            .filter(
                DBEvidenceLifecycleEvent.idempotency_key
                == "ci-lifecycle-identical-retry"
            )
            .all()
        )
        assert len(rows) == 1


def _assert_contradictory_idempotency_reuse_preserves_one_winner() -> None:
    conversion = _register_conversion(_conversion("conflict-conversion"))
    policy = _register_policy(_policy("conflict-policy"))
    shared_key = "ci-lifecycle-contradictory-key"
    results = _run_pair(
        lambda: _apply(
            _action(EvidenceTargetKind.CONVERSION, conversion.id, shared_key)
        ),
        lambda: _apply(
            _action(
                EvidenceTargetKind.STORAGE_POLICY,
                policy.id,
                shared_key,
                action=EvidenceLifecycleAction.REJECTED,
            )
        ),
    )
    successes = [value for _, value in results if not isinstance(value, Exception)]
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert len(successes) == 1, results
    assert len(errors) == 1, results
    assert isinstance(errors[0], ValueError)
    with SessionLocal() as db:
        events = (
            db.query(DBEvidenceLifecycleEvent)
            .filter(DBEvidenceLifecycleEvent.idempotency_key == shared_key)
            .all()
        )
        assert len(events) == 1
        inactive_count = sum(
            not value.active
            for value in (
                db.get(DBIngredientConversionVersion, conversion.id),
                db.get(DBStoragePolicyVersion, policy.id),
            )
        )
        assert inactive_count == 1


def _assert_withdrawal_and_successor_registration_preserve_lineage() -> None:
    baseline = _register_conversion(_conversion("lineage-baseline"))
    document = _action(
        EvidenceTargetKind.CONVERSION,
        baseline.id,
        "ci-lifecycle-withdrawal-successor",
        action=EvidenceLifecycleAction.REJECTED,
    )
    results = _run_pair(
        lambda: _apply(document),
        lambda: _register_conversion(_conversion("lineage-successor", 105.0)),
    )
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    with SessionLocal() as db:
        baseline_row = db.get(DBIngredientConversionVersion, baseline.id)
        successor = (
            db.query(DBIngredientConversionVersion)
            .filter(
                DBIngredientConversionVersion.canonical_name == CONVERSION_NAME,
                DBIngredientConversionVersion.record_version == "lineage-successor",
            )
            .one()
        )
        active = (
            db.query(DBIngredientConversionVersion)
            .filter(
                DBIngredientConversionVersion.canonical_name == CONVERSION_NAME,
                DBIngredientConversionVersion.active.is_(True),
                DBIngredientConversionVersion.evidence_status == "reviewed",
            )
            .all()
        )
        events = (
            db.query(DBEvidenceLifecycleEvent)
            .filter(
                DBEvidenceLifecycleEvent.idempotency_key
                == "ci-lifecycle-withdrawal-successor"
            )
            .all()
        )
        assert baseline_row.active is False
        assert successor.active is True
        assert successor.supersedes_conversion_id == baseline.id
        assert [value.id for value in active] == [successor.id]
        assert len(events) == 1
        assert events[0].conversion_version_id == baseline.id


def main() -> int:
    _reset()
    try:
        _assert_identical_lifecycle_retry_collapses()
        _reset()
        _assert_contradictory_idempotency_reuse_preserves_one_winner()
        _reset()
        _assert_withdrawal_and_successor_registration_preserve_lineage()
        print("Immutable evidence lifecycle PostgreSQL concurrency probe passed")
        return 0
    finally:
        _reset()


if __name__ == "__main__":
    raise SystemExit(main())
