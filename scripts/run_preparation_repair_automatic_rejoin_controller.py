#!/usr/bin/env python3
"""Controlled automatic old-primary rewind/rejoin controller for integration tests."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]
REWIND_SCRIPT = ROOT / "scripts" / "rewind_preparation_repair_old_primary.sh"
VERIFY_SCRIPT = ROOT / "scripts" / "probe_preparation_repair_old_primary_rejoin.py"
DEFAULT_TOPOLOGY_TIMEOUT_SECONDS = 90.0
DEFAULT_GATE_TIMEOUT_SECONDS = 60.0
DEFAULT_COMPLETION_TIMEOUT_SECONDS = 180.0


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"automatic-rejoin state must be an object: {path}")
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


def _run(
    arguments: list[str],
    *,
    timeout_seconds: float,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _docker(arguments: list[str], *, timeout_seconds: float = 20.0):
    return _run(["docker", *arguments], timeout_seconds=timeout_seconds)


def _container_state(container_name: str) -> tuple[bool, bool]:
    result = _docker(
        ["inspect", "-f", "{{.State.Running}}", container_name],
        timeout_seconds=15.0,
    )
    if result.returncode != 0:
        return False, False
    state = result.stdout.strip()
    if state not in {"true", "false"}:
        raise RuntimeError(f"unexpected container state for {container_name}: {state!r}")
    return True, state == "true"


def _volume_exists(volume_name: str) -> bool:
    return _docker(["volume", "inspect", volume_name]).returncode == 0


def _promoted_primary_writable(database_url: str) -> bool:
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        pool_pre_ping=False,
        connect_args={"connect_timeout": 3},
    )
    try:
        with engine.connect() as connection:
            in_recovery, read_only = connection.execute(
                text(
                    "SELECT pg_is_in_recovery(), "
                    "current_setting('transaction_read_only')"
                )
            ).one()
        return in_recovery is False and read_only == "off"
    except Exception:
        return False
    finally:
        engine.dispose()


def _topology_ready(args: argparse.Namespace) -> tuple[bool, dict[str, bool]]:
    old_exists, old_running = _container_state(args.primary_container)
    source_exists, source_running = _container_state(args.promoted_container)
    rejoin_exists, rejoin_running = _container_state(args.rejoin_container)
    volume_retained = _volume_exists(args.primary_volume)
    promoted_writable = (
        source_exists
        and source_running
        and _promoted_primary_writable(args.promoted_database_url)
    )
    facts = {
        "old_primary_container_absent": not old_exists and not old_running,
        "promoted_container_running": source_exists and source_running,
        "promoted_primary_writable": promoted_writable,
        "old_primary_volume_retained": volume_retained,
        "rejoin_container_absent": not rejoin_exists and not rejoin_running,
    }
    return all(facts.values()), facts


def _wait_for_topology(args: argparse.Namespace) -> dict[str, bool]:
    deadline = time.monotonic() + args.topology_timeout_seconds
    last_facts: dict[str, bool] = {}
    while time.monotonic() < deadline:
        witness = _read_json_if_present(args.witness)
        if witness is not None and witness.get("status") == "rejoined":
            return {
                "old_primary_container_absent": True,
                "promoted_container_running": True,
                "promoted_primary_writable": True,
                "old_primary_volume_retained": True,
                "rejoin_container_absent": False,
            }
        ready, last_facts = _topology_ready(args)
        if ready:
            return last_facts
        time.sleep(0.2)
    raise TimeoutError(f"automatic-rejoin topology did not become ready: {last_facts!r}")


def _wait_for_gate(path: Path, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file():
            value = _read_json(path)
            if value.get("released") is True:
                return
        time.sleep(0.05)
    raise TimeoutError(f"automatic-rejoin release gate was not opened: {path}")


def _wait_for_completed_witness(path: Path, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_value: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last_value = _read_json_if_present(path)
        if last_value is not None and last_value.get("status") == "rejoined":
            return last_value
        time.sleep(0.05)
    raise TimeoutError(f"automatic-rejoin witness did not complete: {last_value!r}")


def _report_follower(
    *,
    report_path: Path,
    controller_id: str,
    witness: dict[str, Any],
    lease_contended: bool,
) -> None:
    _write_json_atomically(
        report_path,
        {
            "already_rejoined": not lease_contended,
            "automatic_rejoin_orchestration": True,
            "controller_id": controller_id,
            "lease_acquired": False,
            "lease_contended": lease_contended,
            "rejoin_epoch": int(witness["rejoin_epoch"]),
            "rewind_performed": False,
            "topology_mutation_performed": False,
            "verification_performed": False,
            "winner_controller_id": witness["winner_controller_id"],
            "witness_status": witness["status"],
        },
    )


def _validate_verification_report(path: Path) -> dict[str, Any]:
    report = _read_json(path)
    required_true = {
        "valid",
        "pg_rewind_completed",
        "old_primary_rejoined_as_standby",
        "rejoined_in_recovery",
        "rejoined_transaction_read_only",
        "receiver_streaming",
        "shared_system_identifier",
        "replay_lsn_verified",
        "acceptance_identity_preserved",
        "schedule_identity_preserved",
    }
    missing = sorted(key for key in required_true if report.get(key) is not True)
    if missing:
        raise RuntimeError(f"old-primary verification report lacks true evidence: {missing}")
    if report.get("acceptance_count") != 1 or report.get("replacement_count") != 1:
        raise RuntimeError("old-primary verification report lifecycle counts drifted")
    if report.get("automatic_rejoin_orchestration") is not False:
        raise RuntimeError("underlying manual verifier must not claim automatic orchestration")
    return report


def _run_rejoin_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    environment = os.environ.copy()
    rewind = _run(
        ["bash", str(REWIND_SCRIPT)],
        timeout_seconds=args.rejoin_timeout_seconds,
        environment=environment,
    )
    if rewind.returncode != 0:
        raise RuntimeError(
            "old-primary rewind/rejoin script failed: "
            f"returncode={rewind.returncode}, stdout={rewind.stdout}, stderr={rewind.stderr}"
        )
    required_markers = {
        "isolated_target_crash_recovery=true",
        "stale_recovery_settings_normalized=true",
        "pg_rewind_completed=true",
        "rejoin_in_recovery=t",
        "rejoin_receiver_status=streaming",
        "promoted_sender_count=1",
        "shared_system_identifier=true",
    }
    missing_markers = sorted(
        marker for marker in required_markers if marker not in rewind.stdout
    )
    if missing_markers:
        raise RuntimeError(f"rewind/rejoin output lacks evidence markers: {missing_markers}")

    verify = _run(
        [sys.executable, str(VERIFY_SCRIPT)],
        timeout_seconds=args.verification_timeout_seconds,
        environment=environment,
    )
    if verify.returncode != 0:
        raise RuntimeError(
            "old-primary rejoin verifier failed: "
            f"returncode={verify.returncode}, stdout={verify.stdout}, stderr={verify.stderr}"
        )
    verification = _validate_verification_report(args.verification_report)
    return {
        "isolated_target_crash_recovery": True,
        "stale_recovery_settings_normalized": True,
        "pg_rewind_completed": True,
        "old_primary_rejoined_as_standby": True,
        "rejoined_transaction_read_only": True,
        "receiver_streaming": True,
        "shared_system_identifier": True,
        "replay_lsn_verified": True,
        "acceptance_identity_preserved": True,
        "schedule_identity_preserved": True,
        "acceptance_count": int(verification["acceptance_count"]),
        "replacement_count": int(verification["replacement_count"]),
    }


def run_controller(args: argparse.Namespace) -> int:
    controller_id = args.controller_id or uuid4().hex
    topology = _wait_for_topology(args)
    ready_path = args.ready_directory / f"{controller_id}.json"
    _write_json_atomically(
        ready_path,
        {
            "controller_id": controller_id,
            "ready": True,
            "topology": topology,
        },
    )
    _wait_for_gate(args.release_gate, args.gate_timeout_seconds)

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
                witness=witness,
                lease_contended=True,
            )
            return 0

        existing_witness = _read_json_if_present(args.witness)
        if existing_witness is not None and existing_witness.get("status") == "rejoined":
            _report_follower(
                report_path=args.report,
                controller_id=controller_id,
                witness=existing_witness,
                lease_contended=False,
            )
            return 0

        ready, current_topology = _topology_ready(args)
        if not ready:
            raise RuntimeError(
                "automatic-rejoin topology changed before lease authority: "
                f"{current_topology!r}"
            )

        prior_epoch = 0
        if existing_witness is not None:
            candidate = existing_witness.get("rejoin_epoch")
            if type(candidate) is int and candidate >= 0:
                prior_epoch = candidate
        rejoin_epoch = prior_epoch + 1
        _write_json_atomically(
            args.witness,
            {
                "rejoin_epoch": rejoin_epoch,
                "status": "rejoin_in_progress",
                "winner_controller_id": controller_id,
            },
        )

        pipeline = _run_rejoin_pipeline(args)
        completed_witness = {
            "old_primary_rejoined_as_standby": True,
            "rejoin_epoch": rejoin_epoch,
            "status": "rejoined",
            "winner_controller_id": controller_id,
        }
        _write_json_atomically(args.witness, completed_witness)
        _write_json_atomically(
            args.report,
            {
                "already_rejoined": False,
                "automatic_rejoin_orchestration": True,
                "controller_id": controller_id,
                "distributed_consensus_proven": False,
                "lease_acquired": True,
                "lease_contended": False,
                "partition_safe_fencing_proven": False,
                "production_stonith_proven": False,
                "rejoin_epoch": rejoin_epoch,
                "rewind_performed": True,
                "topology_mutation_performed": True,
                "verification_performed": True,
                "winner_controller_id": controller_id,
                "witness_status": "rejoined",
                **pipeline,
            },
        )
        return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller-id")
    parser.add_argument("--primary-container", required=True)
    parser.add_argument("--promoted-container", required=True)
    parser.add_argument("--primary-volume", required=True)
    parser.add_argument("--rejoin-container", required=True)
    parser.add_argument("--promoted-database-url", required=True)
    parser.add_argument("--ready-directory", type=Path, required=True)
    parser.add_argument("--release-gate", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--verification-report", type=Path, required=True)
    parser.add_argument(
        "--topology-timeout-seconds",
        type=float,
        default=DEFAULT_TOPOLOGY_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--gate-timeout-seconds",
        type=float,
        default=DEFAULT_GATE_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--completion-timeout-seconds",
        type=float,
        default=DEFAULT_COMPLETION_TIMEOUT_SECONDS,
    )
    parser.add_argument("--rejoin-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--verification-timeout-seconds", type=float, default=90.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    numeric_values = {
        "topology_timeout_seconds": args.topology_timeout_seconds,
        "gate_timeout_seconds": args.gate_timeout_seconds,
        "completion_timeout_seconds": args.completion_timeout_seconds,
        "rejoin_timeout_seconds": args.rejoin_timeout_seconds,
        "verification_timeout_seconds": args.verification_timeout_seconds,
    }
    invalid = sorted(
        name
        for name, value in numeric_values.items()
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0
    )
    if invalid:
        raise ValueError(f"automatic-rejoin timeouts must be positive: {invalid}")
    return run_controller(args)


if __name__ == "__main__":
    raise SystemExit(main())
