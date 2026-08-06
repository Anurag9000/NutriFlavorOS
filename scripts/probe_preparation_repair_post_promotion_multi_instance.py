#!/usr/bin/env python3
"""Coordinate six exact-key recovery workers after automatic promotion."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.tests.test_preparation_operations_service import HOUSEHOLD_ID, OWNER_ID
from backend.tests.test_preparation_repair_proposal_acceptance import acceptance_payload


ROOT = Path(__file__).resolve().parents[1]
ROUTER_SCRIPT = ROOT / "scripts" / "probe_preparation_repair_stable_database_endpoint.py"
WORKER_SCRIPT = ROOT / "scripts" / "probe_preparation_repair_multi_instance_recovery.py"
WORKER_COUNT = 6
ONE_COUNTS = {
    "acceptances": 1,
    "replacement_schedules": 1,
    "proposal_accepted_events": 1,
    "replacement_created_events": 1,
}


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required post-promotion variable is missing: {name}")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _wait_for_json(
    path: Path,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    observed: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        if path.is_file():
            observed = _read_json(path)
            if predicate(observed):
                return observed
        time.sleep(0.05)
    raise TimeoutError(f"timed out waiting for {path}: {observed!r}")


def _environment() -> dict[str, str]:
    value = os.environ.copy()
    existing = value.get("PYTHONPATH", "")
    value["PYTHONPATH"] = f"{ROOT}{os.pathsep}{existing}" if existing else str(ROOT)
    return value


def _collect(process: subprocess.Popen[str], timeout_seconds: float) -> tuple[str, str]:
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate(timeout=15)
        raise RuntimeError(
            f"subprocess timed out: pid={process.pid}, stdout={stdout}, stderr={stderr}"
        ) from exc
    if process.returncode != 0:
        raise RuntimeError(
            f"subprocess failed: pid={process.pid}, returncode={process.returncode}, "
            f"stdout={stdout}, stderr={stderr}"
        )
    return stdout, stderr


def _collect_worker(
    process: subprocess.Popen[str],
    result_path: Path,
    timeout_seconds: float,
) -> tuple[str, str]:
    try:
        return _collect(process, timeout_seconds)
    except RuntimeError as exc:
        report = _read_json(result_path) if result_path.is_file() else None
        raise RuntimeError(
            f"post-promotion worker failed: pid={process.pid}, report={report!r}"
        ) from exc


def _ensure_stopped(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
        process.communicate(timeout=15)


def _old_primary_absent(container_name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", container_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode != 0


def _counts(db, proposal_id: int) -> dict[str, int]:
    db.rollback()
    return {
        "acceptances": (
            db.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .count()
        ),
        "replacement_schedules": (
            db.query(DBPersistedPreparationSchedule)
            .filter(DBPersistedPreparationSchedule.source_repair_proposal_id == proposal_id)
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
                DBPersistedPreparationSchedule.id == DBPreparationScheduleEvent.schedule_id,
            )
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id == proposal_id,
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
                "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                "WHERE pid = :backend_pid)"
            ),
            {"backend_pid": backend_pid},
        ).scalar_one()
    )


def _router_events(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("router event must be a JSON object")
            values.append(value)
    return values


def main() -> int:
    promoted_url = _required_environment("FAILOVER_STANDBY_DATABASE_URL")
    stable_url = _required_environment("FAILOVER_STABLE_DATABASE_URL")
    stable_port = int(_required_environment("FAILOVER_STABLE_PORT"))
    standby_port = int(_required_environment("FAILOVER_STANDBY_PORT"))
    primary_container = _required_environment("FAILOVER_PRIMARY_CONTAINER")
    evidence_path = Path(_required_environment("FAILOVER_MULTI_WORKER_REPORT_PATH"))

    if not _old_primary_absent(primary_container):
        raise RuntimeError("old primary container must remain fenced before worker recovery")

    engine = create_engine(
        promoted_url,
        poolclass=NullPool,
        pool_pre_ping=False,
        connect_args={"connect_timeout": 5},
    )
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    db = Session()
    router: subprocess.Popen[str] | None = None
    workers: list[subprocess.Popen[str]] = []

    try:
        if db.execute(text("SELECT pg_is_in_recovery()")).scalar_one() is not False:
            raise RuntimeError("standby endpoint is not the promoted primary")
        if db.execute(text("SHOW transaction_read_only")).scalar_one() != "off":
            raise RuntimeError("promoted primary is not writable")

        acceptances = db.query(DBPreparationRepairProposalAcceptance).all()
        if len(acceptances) != 1:
            raise RuntimeError(f"expected one promoted acceptance, observed {len(acceptances)}")
        acceptance = acceptances[0]
        proposal_id = int(acceptance.proposal_id)
        acceptance_id = int(acceptance.id)
        schedule_id = int(acceptance.created_schedule_id)
        key = str(acceptance.idempotency_key)
        proposal = db.get(DBPreparationRepairProposal, proposal_id)
        if proposal is None:
            raise RuntimeError("promoted proposal is missing")
        payload = acceptance_payload(
            proposal,
            key=key,
            proposal_version=int(acceptance.proposal_version_before),
        )
        if _counts(db, proposal_id) != ONE_COUNTS:
            raise RuntimeError("promoted lifecycle counts are not exactly one")

        with tempfile.TemporaryDirectory(prefix="nutriflavor-post-promotion-") as directory:
            work = Path(directory)
            route_path = work / "route.json"
            ready_path = work / "router-ready.json"
            events_path = work / "router-events.jsonl"
            router_report_path = work / "router-report.json"
            config_path = work / "workers.json"
            gate_path = work / "gate.json"
            _write_json_atomically(
                route_path,
                {
                    "epoch": 1,
                    "target_host": "127.0.0.1",
                    "target_label": "promoted-standby",
                    "target_port": standby_port,
                },
            )
            router = subprocess.Popen(
                [
                    sys.executable,
                    str(ROUTER_SCRIPT),
                    "--listen-port",
                    str(stable_port),
                    "--state",
                    str(route_path),
                    "--ready",
                    str(ready_path),
                    "--events",
                    str(events_path),
                    "--report",
                    str(router_report_path),
                ],
                cwd=ROOT,
                env=_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            ready = _wait_for_json(ready_path, lambda value: value.get("ready") is True)
            if int(ready["listen_port"]) != stable_port or router.poll() is not None:
                raise RuntimeError("post-promotion stable endpoint did not become ready")

            release_token = uuid4().hex
            _write_json_atomically(
                config_path,
                {
                    "database_url": stable_url,
                    "household_id": HOUSEHOLD_ID,
                    "proposal_id": proposal_id,
                    "actor_user_id": OWNER_ID,
                    "release_token": release_token,
                    "payload": payload.model_dump(mode="json"),
                },
            )
            ready_paths: list[Path] = []
            result_paths: list[Path] = []
            for index in range(WORKER_COUNT):
                worker_ready = work / f"ready-{index}.json"
                worker_result = work / f"result-{index}.json"
                ready_paths.append(worker_ready)
                result_paths.append(worker_result)
                workers.append(
                    subprocess.Popen(
                        [
                            sys.executable,
                            str(WORKER_SCRIPT),
                            "--config",
                            str(config_path),
                            "--ready",
                            str(worker_ready),
                            "--gate",
                            str(gate_path),
                            "--result",
                            str(worker_result),
                        ],
                        cwd=ROOT,
                        env=_environment(),
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
            worker_ids = {str(value["worker_instance_id"]) for value in ready_reports}
            backend_pids = {int(value["backend_pid"]) for value in ready_reports}
            if len(worker_ids) != WORKER_COUNT or len(backend_pids) != WORKER_COUNT:
                raise RuntimeError("workers did not establish distinct identities and backends")
            if not all(_backend_exists(db, value) for value in backend_pids):
                raise RuntimeError("not every promoted backend was simultaneously live")

            _write_json_atomically(gate_path, {"release_token": release_token})
            for process, result_path in zip(workers, result_paths, strict=True):
                _collect_worker(process, result_path, 60.0)
            results = [
                _wait_for_json(
                    path,
                    lambda value: value.get("same_key_recovery_performed") is True,
                )
                for path in result_paths
            ]
            if {int(value["acceptance_id"]) for value in results} != {acceptance_id}:
                raise RuntimeError("workers returned different acceptance identities")
            if {int(value["created_schedule_id"]) for value in results} != {schedule_id}:
                raise RuntimeError("workers returned different schedule identities")
            if not all(value["idempotency_key_matches"] is True for value in results):
                raise RuntimeError("a worker did not preserve the exact key")
            if not all(value["pool_checked_out_after_close"] == 0 for value in results):
                raise RuntimeError("a worker leaked a checked-out connection")
            if _counts(db, proposal_id) != ONE_COUNTS:
                raise RuntimeError("post-promotion worker recovery duplicated lifecycle rows")

            router.terminate()
            _collect(router, 30.0)
            router = None
            router_report = _read_json(router_report_path)
            opened = [
                value
                for value in _router_events(events_path)
                if value.get("event") == "connection_opened"
            ]
            if len(opened) < WORKER_COUNT:
                raise RuntimeError("stable endpoint did not observe all worker connections")
            if not all(
                value.get("target_label") == "promoted-standby"
                and value.get("epoch") == 1
                for value in opened
            ):
                raise RuntimeError("a worker connection used the wrong promoted route")
            if router_report["leaked_connection_threads"] != 0:
                raise RuntimeError("post-promotion stable endpoint leaked threads")

        _write_json_atomically(
            evidence_path,
            {
                "valid": True,
                "postgresql_major": 16,
                "staged_after_automatic_promotion": True,
                "old_primary_container_absent": True,
                "stable_application_endpoint": True,
                "route_epoch": 1,
                "route_target": "promoted-standby",
                "application_worker_count": WORKER_COUNT,
                "distinct_worker_instances": True,
                "distinct_live_backend_pids": True,
                "simultaneous_release_gate": True,
                "same_acceptance_identity_for_all_workers": True,
                "same_schedule_identity_for_all_workers": True,
                "pool_checked_out_after_close": 0,
                "acceptance_count": 1,
                "replacement_count": 1,
                "accepted_event_count": 1,
                "created_event_count": 1,
                "distributed_consensus_proven": False,
                "production_stonith_proven": False,
                "representative_production_capacity": False,
                "hosted_green_claim": False,
            },
        )
        return 0
    finally:
        for process in workers:
            _ensure_stopped(process)
        if router is not None:
            _ensure_stopped(router)
        db.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
