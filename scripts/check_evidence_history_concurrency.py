#!/usr/bin/env python3
"""PostgreSQL concurrency probe for immutable food-evidence versions."""

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
from backend.evidence_history_models import (
    DBIngredientConversionVersion,
    DBStoragePolicyVersion,
)
from backend.services.evidence_history_service import (
    register_conversion_version,
    register_storage_policy_version,
)


CONVERSION_NAME = "ci evidence concurrency ingredient"
POLICY_KEY = "ci_evidence_concurrency_policy"


def _conversion(version: str, multiplier: float = 100.0, notes: str | None = None):
    return IngredientConversionVersionInput(
        canonical_name=CONVERSION_NAME,
        from_unit="cup",
        to_unit="g",
        record_version=version,
        multiplier_min=multiplier,
        multiplier_max=multiplier,
        source_name="PostgreSQL concurrency fixture",
        source_url=f"https://example.test/conversion/{version}",
        source_version=version,
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        reviewed_by="CI concurrency probe",
        notes=notes,
        active=True,
    )


def _policy(version: str, hours: float = 24.0, notes: str | None = None):
    return StoragePolicyVersionInput(
        policy_key=POLICY_KEY,
        policy_version=version,
        food_category="CI fixture",
        storage_state="refrigerated",
        duration_min_hours=hours,
        duration_max_hours=hours,
        maximum_temperature_c=4,
        source_name="PostgreSQL concurrency fixture",
        source_url=f"https://example.test/policy/{version}",
        source_version=version,
        evidence_status=EvidenceRecordStatus.REVIEWED,
        reviewed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        reviewed_by="CI concurrency probe",
        safety_scope="test_only",
        notes=notes,
        active=True,
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


def _reset() -> None:
    with SessionLocal() as db:
        db.query(DBIngredientConversionVersion).filter(
            DBIngredientConversionVersion.canonical_name == CONVERSION_NAME
        ).delete(synchronize_session=False)
        db.query(DBStoragePolicyVersion).filter(
            DBStoragePolicyVersion.policy_key == POLICY_KEY
        ).delete(synchronize_session=False)
        db.commit()


def _assert_identical_conversion_retry_collapses() -> None:
    payload = _conversion("identical-v1")
    results = _run_pair(
        lambda: _register_conversion(payload),
        lambda: _register_conversion(payload),
    )
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    assert len({value.id for _, value in results}) == 1
    assert len({value.content_hash for _, value in results}) == 1


def _assert_contradictory_conversion_version_conflicts() -> None:
    results = _run_pair(
        lambda: _register_conversion(
            _conversion("conflict-v1", multiplier=100, notes="left")
        ),
        lambda: _register_conversion(
            _conversion("conflict-v1", multiplier=101, notes="right")
        ),
    )
    successes = [value for _, value in results if not isinstance(value, Exception)]
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert len(successes) == 1, results
    assert len(errors) == 1, results
    assert isinstance(errors[0], ValueError)


def _assert_conversion_successors_form_one_chain() -> None:
    baseline = _register_conversion(_conversion("baseline-v1"))
    results = _run_pair(
        lambda: _register_conversion(_conversion("successor-a", multiplier=102)),
        lambda: _register_conversion(_conversion("successor-b", multiplier=103)),
    )
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    with SessionLocal() as db:
        rows = (
            db.query(DBIngredientConversionVersion)
            .filter(DBIngredientConversionVersion.canonical_name == CONVERSION_NAME)
            .order_by(DBIngredientConversionVersion.id)
            .all()
        )
        active = [
            value
            for value in rows
            if value.active and value.evidence_status == "reviewed"
        ]
        assert len(active) == 1
        successor_rows = [
            value
            for value in rows
            if value.record_version in {"successor-a", "successor-b"}
        ]
        assert len(successor_rows) == 2
        inactive_successor = next(value for value in successor_rows if not value.active)
        assert active[0].supersedes_conversion_id == inactive_successor.id
        assert inactive_successor.supersedes_conversion_id == baseline.id


def _assert_policy_successors_form_one_chain() -> None:
    baseline = _register_policy(_policy("baseline-v1"))
    results = _run_pair(
        lambda: _register_policy(_policy("successor-a", hours=30)),
        lambda: _register_policy(_policy("successor-b", hours=36)),
    )
    errors = [value for _, value in results if isinstance(value, Exception)]
    assert errors == [], errors
    with SessionLocal() as db:
        rows = (
            db.query(DBStoragePolicyVersion)
            .filter(DBStoragePolicyVersion.policy_key == POLICY_KEY)
            .order_by(DBStoragePolicyVersion.id)
            .all()
        )
        active = [
            value
            for value in rows
            if value.active and value.evidence_status == "reviewed"
        ]
        assert len(active) == 1
        successor_rows = [
            value
            for value in rows
            if value.policy_version in {"successor-a", "successor-b"}
        ]
        assert len(successor_rows) == 2
        inactive_successor = next(value for value in successor_rows if not value.active)
        assert active[0].supersedes_policy_id == inactive_successor.id
        assert inactive_successor.supersedes_policy_id == baseline.id


def main() -> int:
    _reset()
    try:
        _assert_identical_conversion_retry_collapses()
        _assert_contradictory_conversion_version_conflicts()
        _assert_conversion_successors_form_one_chain()
        _assert_policy_successors_form_one_chain()
        print("Immutable food-evidence PostgreSQL concurrency probe passed")
        return 0
    finally:
        _reset()


if __name__ == "__main__":
    raise SystemExit(main())
