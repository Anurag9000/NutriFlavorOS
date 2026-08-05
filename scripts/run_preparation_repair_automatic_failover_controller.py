#!/usr/bin/env python3
"""Controlled single-witness PostgreSQL failover controller for integration tests."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool


DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_PROBE_INTERVAL_SECONDS = 0.2
DEFAULT_DETECTION_TIMEOUT_SECONDS = 60.0
DEFAULT_COMPLETION_TIMEOUT_SECONDS = 90.0


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"controller state must be an object: {path}")
    return value


def _read_json_if_present(path: Path) -> dict[str, Any] | None:
    return _read_json(path) if path.is_file() else None


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _run_docker(arguments: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _container_state(container_name: str) -> tuple[bool, bool]:
    result = _run_docker(
        ["inspect", "-f", "{{.State.Running}}", container_name],
        timeout=15.0,
    )
    if result.returncode != 0:
        return False, False
    value = result.stdout.strip()
    if value not in {"true", "false"}:
        raise RuntimeError(f"unexpected Docker running state: {value!r}")
    return True, value == "true"


def _volume_exists(volume_name: str) -> bool:
    return _run_docker(["volume", "inspect", volume_name], timeout=15.0).returncode == 0


def _probe_primary(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _wait_for_primary_failure(
    *,
    host: str,
    port: int,
    threshold: int,
    interval_seconds: float,
    timeout_seconds: float,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    consecutive_failures = 0
    total_failures = 0
    while time.monotonic() < deadline:
        if _probe_primary(host, port):
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            total_failures += 1
            if consecutive_failures >= threshold:
                return total_failures
        time.sleep(interval_seconds)
    raise TimeoutError(
        "primary failure threshold was not reached: "
        f"host={host}, port={port}, threshold={threshold}"
    )


def _wait_for_completed_witness(path: Path, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_value: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last_value = _read_json_if_present(path)
        if last_value is not None and last_value.get("status") == "promoted":
            return last_value
        time.sleep(0.05)
    raise TimeoutError(f"failover witness did not reach promoted state: {last_value!r}")


def _fence_old_primary(*, container_name: str, volume_name: str) -> dict[str, Any]:
    exists_before, running_before = _container_state(container_name)
    if not exists_before:
        raise RuntimeError("old primary container disappeared before fencing authority")
    if running_before:
        raise RuntimeError("old primary is still running; promotion is forbidden")

    removal = _run_docker(["rm", "-f", container_name], timeout=30.0)
    if removal.returncode != 0:
        raise RuntimeError(f"old primary container fencing failed: {removal.stderr}")
    exists_after, running_after = _container_state(container_name)
    if exists_after or running_after:
        raise RuntimeError("old primary container remained addressable after fencing")
    if not _volume_exists(volume_name):
        raise RuntimeError("old primary data volume was not retained for forensic recovery")

    return {
        "old_primary_container_existed_before_fence": exists_before,
        "old_primary_running_before_fence": running_before,
        "old_primary_container_removed": True,
        "old_primary_running_after_fence": False,
        "old_primary_volume_retained": True,
    }


def _promote_standby(database_url: str) -> dict[str, Any]:
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        pool_pre_ping=False,
        connect_args={"connect_timeout": 5},
    )
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            promoted = connection.execute(text("SELECT pg_promote(true, 60)")).scalar_one()
        if promoted is not True:
            raise RuntimeError("standby promotion did not report success")

        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            with engine.connect() as connection:
                in_recovery, read_only = connection.execute(
                    text(
                        "SELECT pg_is_in_recovery(), "
                        "current_setting('transaction_read_only')"
                    )
                ).one()
                if in_recovery is False and read_only == "off":
                    system_identifier = str(
                        connection.execute(
                            text(
                                "SELECT system_identifier::text "
                                "FROM pg_control_system()"
                            )
                        ).scalar_one()
                    )
                    timeline = str(
                        connection.execute(
                            text(
                                "SELECT substring("
                                "pg_walfile_name(pg_current_wal_lsn()) from 1 for 8)"
                            )
                        ).scalar_one()
                    )
                    return {
                        "promoted_system_identifier": system_identifier,
                        "promoted_timeline": timeline,
                        "standby_promoted": True,
                        "transaction_read_only": read_only,
                    }
            time.sleep(0.1)
        raise TimeoutError("standby did not become a writable primary after promotion")
    finally:
        engine.dispose()


def _route_for_promoted_endpoint(
    *,
    standby_database_url: str,
    epoch: int,
    controller_id: str,
) -> dict[str, Any]:
    parsed = make_url(standby_database_url)
    host = parsed.host or "127.0.0.1"
    port = int(parsed.port or 5432)
    return {
        "controller_id": controller_id,
        "epoch": epoch,
        "target_host": host,
        "target_label": "promoted-standby",
        "target_port": port,
    }


def _report_follower(
    *,
    report_path: Path,
    controller_id: str,
    failure_observations: int,
    witness: dict[str, Any],
    lease_contended: bool,
) -> None:
    _write_json_atomically(
        report_path,
        {
            "already_promoted": not lease_contended,
            "automatic_failure_detection": True,
            "controller_id": controller_id,
            "failure_observations": failure_observations,
            "fence_epoch": int(witness["epoch"]),
            "lease_acquired": False,
            "lease_contended": lease_contended,
            "promotion_performed": False,
            "route_rotation_performed": False,
            "winner_controller_id": witness["winner_controller_id"],
            "witness_status": witness["status"],
        },
    )


def run_controller(args: argparse.Namespace) -> int:
    controller_id = args.controller_id or uuid4().hex
    failure_observations = _wait_for_primary_failure(
        host=args.primary_host,
        port=args.primary_port,
        threshold=args.failure_threshold,
        interval_seconds=args.probe_interval_seconds,
        timeout_seconds=args.detection_timeout_seconds,
    )

    args.lease.parent.mkdir(parents=True, exist_ok=True)
    with args.lease.open("a+", encoding="utf-8") as lease_stream:
        try:
            fcntl.flock(lease_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            witness = _wait_for_completed_witness(
                args.witness,
                args.completion_timeout_seconds,
            )
            _report_follower(
                report_path=args.report,
                controller_id=controller_id,
                failure_observations=failure_observations,
                witness=witness,
                lease_contended=True,
            )
            return 0

        existing_witness = _read_json_if_present(args.witness)
        if existing_witness is not None and existing_witness.get("status") == "promoted":
            _report_follower(
                report_path=args.report,
                controller_id=controller_id,
                failure_observations=failure_observations,
                witness=existing_witness,
                lease_contended=False,
            )
            return 0

        route_state = _read_json(args.route_state)
        route_epoch = route_state.get("epoch")
        if type(route_epoch) is not int or route_epoch < 0:
            raise ValueError("stable endpoint route epoch must be a nonnegative integer")
        if route_state.get("target_label") != "original-primary":
            raise RuntimeError("automatic failover may start only from original-primary route")

        prior_epoch = -1
        if existing_witness is not None:
            candidate = existing_witness.get("epoch")
            if type(candidate) is int:
                prior_epoch = candidate
        epoch = max(route_epoch, prior_epoch) + 1
        _write_json_atomically(
            args.witness,
            {
                "epoch": epoch,
                "status": "promotion_in_progress",
                "winner_controller_id": controller_id,
            },
        )

        fence_report = _fence_old_primary(
            container_name=args.primary_container,
            volume_name=args.primary_volume,
        )
        promotion_report = _promote_standby(args.standby_database_url)
        promoted_route = _route_for_promoted_endpoint(
            standby_database_url=args.standby_database_url,
            epoch=epoch,
            controller_id=controller_id,
        )
        _write_json_atomically(args.route_state, promoted_route)

        completed_witness = {
            "epoch": epoch,
            "old_primary_container_removed": True,
            "old_primary_volume_retained": True,
            "route_target_label": "promoted-standby",
            "status": "promoted",
            "winner_controller_id": controller_id,
        }
        _write_json_atomically(args.witness, completed_witness)
        _write_json_atomically(
            args.report,
            {
                "already_promoted": False,
                "automatic_failure_detection": True,
                "controller_id": controller_id,
                "failure_observations": failure_observations,
                "failure_threshold": args.failure_threshold,
                "fence_epoch": epoch,
                "lease_acquired": True,
                "lease_contended": False,
                "promotion_performed": True,
                "route_rotation_performed": True,
                "server_automatic_mutation_retry": False,
                "witness_status": "promoted",
                "winner_controller_id": controller_id,
                **fence_report,
                **promotion_report,
            },
        )
        return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-host", required=True)
    parser.add_argument("--primary-port", type=int, required=True)
    parser.add_argument("--standby-database-url", required=True)
    parser.add_argument("--primary-container", required=True)
    parser.add_argument("--primary-volume", required=True)
    parser.add_argument("--route-state", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--controller-id")
    parser.add_argument("--failure-threshold", type=int, default=DEFAULT_FAILURE_THRESHOLD)
    parser.add_argument(
        "--probe-interval-seconds",
        type=float,
        default=DEFAULT_PROBE_INTERVAL_SECONDS,
    )
    parser.add_argument(
        "--detection-timeout-seconds",
        type=float,
        default=DEFAULT_DETECTION_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--completion-timeout-seconds",
        type=float,
        default=DEFAULT_COMPLETION_TIMEOUT_SECONDS,
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.failure_threshold < 2:
        raise ValueError("failure threshold must require at least two observations")
    if args.probe_interval_seconds <= 0:
        raise ValueError("probe interval must be positive")
    if args.detection_timeout_seconds <= 0 or args.completion_timeout_seconds <= 0:
        raise ValueError("controller timeouts must be positive")
    return run_controller(args)


if __name__ == "__main__":
    raise SystemExit(main())
