from __future__ import annotations

import json
import os
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
    / "probe_preparation_repair_worker_recycle.py"
)


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
        f"timed out waiting for worker report {path}: {last_value!r}"
    )


def _accepted_counts(db, proposal_id: int) -> dict[str, int]:
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
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not _backend_exists(db, backend_pid):
            return
        time.sleep(0.05)
    raise AssertionError(
        f"recycled worker PostgreSQL backend {backend_pid} remained active"
    )


def _worker_environment(repo_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{existing}" if existing else str(repo_root)
    )
    return environment


def test_postgres_worker_recycle_under_pool_pressure_recovers_exact_request(
    db,
    tmp_path: Path,
):
    assert db.get_bind().dialect.name == "postgresql", (
        "Worker recycle evidence must run on PostgreSQL"
    )
    _, _, proposal = create_proposal(db)
    idempotency_key = "pg-worker-recycle-exact-key"
    payload = acceptance_payload(proposal, key=idempotency_key)
    repo_root = Path(__file__).resolve().parents[2]

    config_path = tmp_path / "worker-recycle-config.json"
    pressure_report_path = tmp_path / "worker-pressure-report.json"
    recovery_report_path = tmp_path / "worker-recovery-report.json"
    config_path.write_text(
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

    environment = _worker_environment(repo_root)
    pressure_process = subprocess.Popen(
        [
            sys.executable,
            str(WORKER_SCRIPT),
            "pressure",
            "--config",
            str(config_path),
            "--report",
            str(pressure_report_path),
        ],
        cwd=repo_root,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        pressure_report = _wait_for_json(
            pressure_report_path,
            lambda value: value.get("waiting_for_orderly_recycle") is True,
        )
        assert pressure_process.poll() is None
        assert pressure_report == {
            "mode": "pressure",
            "worker_pid": pressure_process.pid,
            "holder_backend_pid": pressure_report["holder_backend_pid"],
            "pool_checked_out": 1,
            "code": "database_pool_timeout",
            "retry_safe": True,
            "no_transaction_started": True,
            "outcome_unknown": False,
            "will_retry": False,
            "attempt": 1,
            "lifecycle_mutation_performed": False,
            "waiting_for_orderly_recycle": True,
            "recycle_completed": False,
        }
        old_backend_pid = int(pressure_report["holder_backend_pid"])
        assert _backend_exists(db, old_backend_pid) is True

        db.expire_all()
        assert _accepted_counts(db, proposal.id) == {
            "acceptances": 0,
            "replacement_schedules": 0,
            "proposal_accepted_events": 0,
            "replacement_created_events": 0,
        }

        assert pressure_process.stdin is not None
        pressure_process.stdin.close()
        assert pressure_process.wait(timeout=15) == 0
        recycled_report = _wait_for_json(
            pressure_report_path,
            lambda value: value.get("recycle_completed") is True,
        )
        assert recycled_report["waiting_for_orderly_recycle"] is False
        assert recycled_report["pool_checked_out_after_close"] == 0
        _wait_for_backend_absence(db, old_backend_pid)
    finally:
        if pressure_process.poll() is None:
            if pressure_process.stdin is not None:
                pressure_process.stdin.close()
            pressure_process.wait(timeout=15)

    recovery = subprocess.run(
        [
            sys.executable,
            str(WORKER_SCRIPT),
            "recover",
            "--config",
            str(config_path),
            "--report",
            str(recovery_report_path),
        ],
        cwd=repo_root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    assert recovery.returncode == 0, recovery.stderr
    recovery_report = _wait_for_json(
        recovery_report_path,
        lambda value: value.get("same_key_recovery_performed") is True,
    )
    assert recovery_report["mode"] == "recovery"
    assert recovery_report["worker_pid"] != pressure_process.pid
    assert recovery_report["recovery_backend_pid"] != old_backend_pid
    assert recovery_report["created_schedule_status"] == "draft"
    assert recovery_report["created_schedule_version"] == 1
    assert recovery_report["pool_checked_out_after_close"] == 0

    db.expire_all()
    assert _accepted_counts(db, proposal.id) == {
        "acceptances": 1,
        "replacement_schedules": 1,
        "proposal_accepted_events": 1,
        "replacement_created_events": 1,
    }

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
