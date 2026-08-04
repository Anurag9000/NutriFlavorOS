from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import text

from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
)
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


WORKER_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "probe_preparation_repair_worker_crash.py"
)
ZERO_COUNTS = {
    "acceptances": 0,
    "replacement_schedules": 0,
    "proposal_accepted_events": 0,
    "replacement_created_events": 0,
}
ONE_COUNTS = {
    "acceptances": 1,
    "replacement_schedules": 1,
    "proposal_accepted_events": 1,
    "replacement_created_events": 1,
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _wait_for_json(
    path: Path,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout_seconds: float = 20,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_value: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        if path.is_file():
            last_value = _read_json(path)
            if predicate(last_value):
                return last_value
        time.sleep(0.05)
    raise AssertionError(
        f"timed out waiting for crash-worker report {path}: {last_value!r}"
    )


def _accepted_counts(db, proposal_id: int) -> dict[str, int]:
    db.rollback()
    return {
        "acceptances": (
            db.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .count()
        ),
        "replacement_schedules": (
            db.query(DBPersistedPreparationSchedule)
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == proposal_id
            )
            .count()
        ),
        "proposal_accepted_events": (
            db.query(DBPreparationRepairProposalEvent)
            .filter(
                DBPreparationRepairProposalEvent.proposal_id == proposal_id,
                DBPreparationRepairProposalEvent.event_type == "accepted",
            )
            .count()
        ),
        "replacement_created_events": (
            db.query(DBPreparationScheduleEvent)
            .join(
                DBPersistedPreparationSchedule,
                DBPersistedPreparationSchedule.id
                == DBPreparationScheduleEvent.schedule_id,
            )
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == proposal_id,
                DBPreparationScheduleEvent.event_type == "created",
            )
            .count()
        ),
    }


def _proposal_status(db, proposal_id: int) -> str:
    db.rollback()
    proposal = db.get(DBPreparationRepairProposal, proposal_id)
    assert proposal is not None
    db.refresh(proposal)
    return str(proposal.status)


def _backend_exists(db, backend_pid: int) -> bool:
    db.rollback()
    return bool(
        db.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_stat_activity WHERE pid = :backend_pid"
                ")"
            ),
            {"backend_pid": backend_pid},
        ).scalar_one()
    )


def _wait_for_backend_absence(db, backend_pid: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not _backend_exists(db, backend_pid):
            return
        time.sleep(0.05)
    raise AssertionError(
        f"crashed worker PostgreSQL backend {backend_pid} remained active"
    )


def _worker_environment(repo_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{existing}" if existing else str(repo_root)
    )
    return environment


def _write_config(db, tmp_path: Path, proposal, idempotency_key: str) -> Path:
    payload = acceptance_payload(proposal, key=idempotency_key)
    path = tmp_path / f"worker-crash-{proposal.id}-config.json"
    path.write_text(
        json.dumps(
            {
                "database_url": db.get_bind().url.render_as_string(
                    hide_password=False
                ),
                "household_id": HOUSEHOLD_ID,
                "proposal_id": proposal.id,
                "actor_user_id": OWNER_ID,
                "payload": payload.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _start_worker(
    mode: str,
    *,
    config_path: Path,
    report_path: Path,
    repo_root: Path,
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            str(WORKER_SCRIPT),
            mode,
            "--config",
            str(config_path),
            "--report",
            str(report_path),
        ],
        cwd=repo_root,
        env=_worker_environment(repo_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _collect_worker_output(process: subprocess.Popen[str]) -> tuple[str, str]:
    stdout, stderr = process.communicate(timeout=5)
    return stdout or "", stderr or ""


def _kill_worker(process: subprocess.Popen[str]) -> None:
    assert process.poll() is None
    os.kill(process.pid, signal.SIGKILL)
    return_code = process.wait(timeout=15)
    assert return_code == -signal.SIGKILL


def _ensure_worker_stopped(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        os.kill(process.pid, signal.SIGKILL)
        process.wait(timeout=15)
    _collect_worker_output(process)


def _recover(
    *,
    config_path: Path,
    report_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            str(WORKER_SCRIPT),
            "recover",
            "--config",
            str(config_path),
            "--report",
            str(report_path),
        ],
        cwd=repo_root,
        env=_worker_environment(repo_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return _wait_for_json(
        report_path,
        lambda value: value.get("same_key_recovery_performed") is True,
    )


def _assert_exact_recovery(
    db,
    *,
    proposal,
    idempotency_key: str,
    recovery_report: dict[str, Any],
) -> None:
    assert recovery_report["mode"] == "recovery"
    assert len(str(recovery_report["worker_instance_id"])) == 32
    assert recovery_report["created_schedule_status"] == "draft"
    assert recovery_report["created_schedule_version"] == 1
    assert recovery_report["pool_checked_out_after_close"] == 0

    assert _accepted_counts(db, proposal.id) == ONE_COUNTS
    assert _proposal_status(db, proposal.id) == "accepted"

    payload = acceptance_payload(proposal, key=idempotency_key)
    replayed = accept_repair_proposal_with_source_guard(
        db,
        household_id=HOUSEHOLD_ID,
        proposal_id=proposal.id,
        actor_user_id=OWNER_ID,
        payload=payload,
    )
    assert replayed.acceptance.id == recovery_report["acceptance_id"]
    assert (
        replayed.acceptance.created_schedule_id
        == recovery_report["created_schedule_id"]
    )
    assert replayed.acceptance.idempotency_key == idempotency_key
    assert _accepted_counts(db, proposal.id) == ONE_COUNTS

    proposal_events = (
        db.query(DBPreparationRepairProposalEvent)
        .filter(DBPreparationRepairProposalEvent.proposal_id == proposal.id)
        .order_by(DBPreparationRepairProposalEvent.id)
        .all()
    )
    assert [value.event_type for value in proposal_events] == [
        "created",
        "accepted",
    ]


def test_postgres_sigkill_during_pool_checkout_recovers_exact_request(
    db,
    tmp_path: Path,
):
    assert db.get_bind().dialect.name == "postgresql"
    _, _, proposal = create_proposal(db)
    idempotency_key = "pg-worker-checkout-crash-exact-key"
    repo_root = Path(__file__).resolve().parents[2]
    config_path = _write_config(db, tmp_path, proposal, idempotency_key)
    crash_report_path = tmp_path / "checkout-crash-report.json"
    recovery_report_path = tmp_path / "checkout-crash-recovery.json"

    process = _start_worker(
        "checkout-crash",
        config_path=config_path,
        report_path=crash_report_path,
        repo_root=repo_root,
    )
    try:
        report = _wait_for_json(
            crash_report_path,
            lambda value: value.get("waiting_for_sigkill") is True,
        )
        old_worker_instance_id = str(report["worker_instance_id"])
        old_backend_pid = int(report["holder_backend_pid"])
        assert len(old_worker_instance_id) == 32
        assert report["worker_pid"] == process.pid
        assert report["pool_checked_out"] == 1
        assert report["code"] == "database_pool_timeout"
        assert report["retry_safe"] is True
        assert report["no_transaction_started"] is True
        assert report["outcome_unknown"] is False
        assert report["will_retry"] is False
        assert report["lifecycle_mutation_performed"] is False
        assert _backend_exists(db, old_backend_pid) is True
        assert _accepted_counts(db, proposal.id) == ZERO_COUNTS
        assert _proposal_status(db, proposal.id) == "proposed"

        _kill_worker(process)
    finally:
        _ensure_worker_stopped(process)

    _wait_for_backend_absence(db, old_backend_pid)
    assert _accepted_counts(db, proposal.id) == ZERO_COUNTS
    assert _proposal_status(db, proposal.id) == "proposed"

    recovery_report = _recover(
        config_path=config_path,
        report_path=recovery_report_path,
        repo_root=repo_root,
    )
    assert recovery_report["worker_instance_id"] != old_worker_instance_id
    assert recovery_report["recovery_backend_pid"] != old_backend_pid
    _assert_exact_recovery(
        db,
        proposal=proposal,
        idempotency_key=idempotency_key,
        recovery_report=recovery_report,
    )


def test_postgres_sigkill_after_flush_rolls_back_then_recovers_exact_request(
    db,
    tmp_path: Path,
):
    assert db.get_bind().dialect.name == "postgresql"
    _, _, proposal = create_proposal(db)
    idempotency_key = "pg-worker-open-transaction-crash-exact-key"
    repo_root = Path(__file__).resolve().parents[2]
    config_path = _write_config(db, tmp_path, proposal, idempotency_key)
    crash_report_path = tmp_path / "transaction-crash-report.json"
    recovery_report_path = tmp_path / "transaction-crash-recovery.json"

    process = _start_worker(
        "transaction-crash",
        config_path=config_path,
        report_path=crash_report_path,
        repo_root=repo_root,
    )
    try:
        report = _wait_for_json(
            crash_report_path,
            lambda value: value.get("transaction_flushed_before_crash") is True,
        )
        old_worker_instance_id = str(report["worker_instance_id"])
        old_backend_pid = int(report["backend_pid"])
        assert len(old_worker_instance_id) == 32
        assert report["worker_pid"] == process.pid
        assert report["pool_checked_out"] == 1
        assert report["commit_method_intercepted"] is True
        assert report["database_commit_statement_started"] is False
        assert report["transaction_local_counts"] == ONE_COUNTS
        assert report["transaction_local_proposal_status"] == "accepted"
        assert report["waiting_for_sigkill"] is True
        assert report["lifecycle_commit_performed"] is False
        assert _backend_exists(db, old_backend_pid) is True

        # The child transaction sees its flushed rows, while an independent
        # committed read sees the original proposal and zero lifecycle mutation.
        assert _accepted_counts(db, proposal.id) == ZERO_COUNTS
        assert _proposal_status(db, proposal.id) == "proposed"

        _kill_worker(process)
    finally:
        _ensure_worker_stopped(process)

    _wait_for_backend_absence(db, old_backend_pid)
    assert _accepted_counts(db, proposal.id) == ZERO_COUNTS
    assert _proposal_status(db, proposal.id) == "proposed"

    recovery_report = _recover(
        config_path=config_path,
        report_path=recovery_report_path,
        repo_root=repo_root,
    )
    assert recovery_report["worker_instance_id"] != old_worker_instance_id
    assert recovery_report["recovery_backend_pid"] != old_backend_pid
    _assert_exact_recovery(
        db,
        proposal=proposal,
        idempotency_key=idempotency_key,
        recovery_report=recovery_report,
    )
