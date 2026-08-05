from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.api.database_error_handlers import classify_operational_error
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
from backend.tests.postgres_commit_ack_drop_proxy import PostgresCommitAckDropProxy
from backend.tests.postgres_preparation_fixture import postgres_db as db
from backend.tests.test_preparation_operations_service import HOUSEHOLD_ID, OWNER_ID
from backend.tests.test_preparation_repair_proposal_acceptance import (
    acceptance_payload,
    create_proposal,
)


WORKER_COUNT = 6
WORKER_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "probe_preparation_repair_multi_instance_recovery.py"
)
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
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_value: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        if path.is_file():
            last_value = _read_json(path)
            if predicate(last_value):
                return last_value
        time.sleep(0.02)
    raise AssertionError(
        f"timed out waiting for multi-instance report {path}: {last_value!r}"
    )


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _worker_environment(repo_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{existing}" if existing else str(repo_root)
    )
    return environment


def _proxy_database_url(db, proxy_port: int):
    direct_url = db.get_bind().url
    query = dict(direct_url.query)
    query.update(
        {
            "connect_timeout": "5",
            "gssencmode": "disable",
            "sslmode": "disable",
        }
    )
    return direct_url.set(host="127.0.0.1", port=proxy_port, query=query)


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


def _commit_once_without_acknowledgement(db, proposal, payload) -> OperationalError:
    direct_url = db.get_bind().url
    proxy = PostgresCommitAckDropProxy(
        upstream_host=direct_url.host or "127.0.0.1",
        upstream_port=int(direct_url.port or 5432),
    )
    captured_error: OperationalError | None = None
    with proxy:
        proxy.wait_until_ready()
        engine = create_engine(
            _proxy_database_url(db, proxy.listen_port),
            poolclass=NullPool,
            pool_pre_ping=False,
        )
        Session = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        worker = Session()
        try:
            worker.execute(text("SET LOCAL synchronous_commit = on"))
            assert worker.execute(text("SHOW synchronous_commit")).scalar_one() == "on"
            with pytest.raises(OperationalError) as caught:
                accept_repair_proposal_with_source_guard(
                    worker,
                    household_id=HOUSEHOLD_ID,
                    proposal_id=proposal.id,
                    actor_user_id=OWNER_ID,
                    payload=payload,
                )
            captured_error = caught.value
            proxy.wait_for_commit_ack_drop()
        finally:
            worker.close()
            engine.dispose()

    assert captured_error is not None
    report = proxy.report()
    assert report.commit_query_forwarded is True
    assert report.commit_command_complete_seen is True
    assert report.commit_acknowledgement_forwarded is False
    assert report.proxy_threads_stopped is True
    return captured_error


def test_postgres_ambiguous_commit_converges_across_six_application_instances(
    db,
    tmp_path: Path,
):
    assert db.get_bind().dialect.name == "postgresql"
    _, _, proposal = create_proposal(db)
    idempotency_key = "pg-multi-instance-ambiguous-commit-exact-key"
    payload = acceptance_payload(proposal, key=idempotency_key)

    captured_error = _commit_once_without_acknowledgement(db, proposal, payload)
    classification = classify_operational_error(captured_error)
    assert classification["code"] == "database_commit_outcome_unknown"
    assert classification["retryable"] is True
    assert classification["retry_safe"] is False
    assert classification["outcome_unknown"] is True
    assert classification["automatic_retry_performed"] is False
    assert captured_error.connection_invalidated is True
    assert _accepted_counts(db, proposal.id) == ONE_COUNTS

    acceptance = (
        db.query(DBPreparationRepairProposalAcceptance)
        .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal.id)
        .one()
    )
    committed_acceptance_id = int(acceptance.id)
    committed_schedule_id = int(acceptance.created_schedule_id)

    repo_root = Path(__file__).resolve().parents[2]
    release_token = uuid4().hex
    config_path = tmp_path / "multi-instance-recovery-config.json"
    gate_path = tmp_path / "multi-instance-release-gate.json"
    config_path.write_text(
        json.dumps(
            {
                "database_url": db.get_bind().url.render_as_string(
                    hide_password=False
                ),
                "household_id": HOUSEHOLD_ID,
                "proposal_id": proposal.id,
                "actor_user_id": OWNER_ID,
                "release_token": release_token,
                "payload": payload.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    processes: list[subprocess.Popen[str]] = []
    ready_paths: list[Path] = []
    result_paths: list[Path] = []
    try:
        for index in range(WORKER_COUNT):
            ready_path = tmp_path / f"multi-instance-ready-{index}.json"
            result_path = tmp_path / f"multi-instance-result-{index}.json"
            ready_paths.append(ready_path)
            result_paths.append(result_path)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(WORKER_SCRIPT),
                        "--config",
                        str(config_path),
                        "--ready",
                        str(ready_path),
                        "--gate",
                        str(gate_path),
                        "--result",
                        str(result_path),
                    ],
                    cwd=repo_root,
                    env=_worker_environment(repo_root),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )

        ready_reports = [
            _wait_for_json(
                path,
                lambda value: value.get("waiting_for_release_gate") is True,
            )
            for path in ready_paths
        ]
        assert len(ready_reports) == WORKER_COUNT
        assert {value["worker_pid"] for value in ready_reports} == {
            process.pid for process in processes
        }
        worker_instance_ids = {
            str(value["worker_instance_id"]) for value in ready_reports
        }
        backend_pids = {int(value["backend_pid"]) for value in ready_reports}
        assert len(worker_instance_ids) == WORKER_COUNT
        assert all(len(value) == 32 for value in worker_instance_ids)
        assert len(backend_pids) == WORKER_COUNT
        assert all(_backend_exists(db, value) for value in backend_pids)

        _write_json_atomically(gate_path, {"release_token": release_token})

        for process in processes:
            return_code = process.wait(timeout=45)
            if return_code != 0:
                stderr = process.stderr.read() if process.stderr is not None else ""
                raise AssertionError(
                    f"multi-instance recovery worker failed: {return_code}: {stderr}"
                )

        result_reports = [
            _wait_for_json(
                path,
                lambda value: value.get("same_key_recovery_performed") is True,
            )
            for path in result_paths
        ]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=15)

    assert len(result_reports) == WORKER_COUNT
    assert {int(value["acceptance_id"]) for value in result_reports} == {
        committed_acceptance_id
    }
    assert {int(value["created_schedule_id"]) for value in result_reports} == {
        committed_schedule_id
    }
    assert {str(value["created_schedule_status"]) for value in result_reports} == {
        "draft"
    }
    assert {int(value["created_schedule_version"]) for value in result_reports} == {1}
    assert all(value["idempotency_key_matches"] is True for value in result_reports)
    assert all(value["pool_checked_out_after_close"] == 0 for value in result_reports)
    assert {str(value["worker_instance_id"]) for value in result_reports} == (
        worker_instance_ids
    )
    assert {int(value["backend_pid"]) for value in result_reports} == backend_pids

    assert _accepted_counts(db, proposal.id) == ONE_COUNTS
    proposal_row = db.get(DBPreparationRepairProposal, proposal.id)
    assert proposal_row is not None
    db.refresh(proposal_row)
    assert proposal_row.status == "accepted"

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
