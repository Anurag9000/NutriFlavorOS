#!/usr/bin/env python3
"""Run two controlled automatic old-primary rejoin controllers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "scripts" / "run_preparation_repair_automatic_rejoin_controller.py"
CONTROLLER_COUNT = 2


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required automatic-rejoin variable is missing: {name}")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"automatic-rejoin JSON must be an object: {path}")
    return value


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _wait_for_ready_files(
    directory: Path,
    controller_ids: list[str],
    processes: list[subprocess.Popen[str]],
    timeout_seconds: float = 90.0,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        exited = [
            (controller_ids[index], process.returncode)
            for index, process in enumerate(processes)
            if process.poll() is not None
        ]
        if exited:
            raise RuntimeError(
                "automatic-rejoin controller exited before publishing readiness: "
                f"{exited}"
            )
        ready_paths = [directory / f"{controller_id}.json" for controller_id in controller_ids]
        if all(path.is_file() for path in ready_paths):
            reports = [_read_json(path) for path in ready_paths]
            if all(report.get("ready") is True for report in reports):
                return reports
        time.sleep(0.05)
    raise TimeoutError("automatic-rejoin controllers did not become simultaneously ready")


def _collect_process(
    process: subprocess.Popen[str],
    *,
    controller_id: str,
    timeout_seconds: float = 240.0,
) -> tuple[str, str]:
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate(timeout=15)
        raise RuntimeError(
            "automatic-rejoin controller timed out: "
            f"controller={controller_id}, stdout={stdout}, stderr={stderr}"
        ) from exc
    if process.returncode != 0:
        raise RuntimeError(
            "automatic-rejoin controller failed: "
            f"controller={controller_id}, returncode={process.returncode}, "
            f"stdout={stdout}, stderr={stderr}"
        )
    return stdout, stderr


def _ensure_process_stopped(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
        process.communicate(timeout=15)


def _validate_controller_reports(
    reports: list[dict[str, Any]],
    witness: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    winners = [report for report in reports if report.get("lease_acquired") is True]
    followers = [report for report in reports if report.get("lease_acquired") is False]
    if len(winners) != 1 or len(followers) != 1:
        raise RuntimeError(
            "automatic-rejoin authority partition drifted: "
            f"winners={len(winners)}, followers={len(followers)}"
        )
    winner = winners[0]
    follower = followers[0]
    required_winner_true = {
        "automatic_rejoin_orchestration",
        "rewind_performed",
        "topology_mutation_performed",
        "verification_performed",
        "isolated_target_crash_recovery",
        "stale_recovery_settings_normalized",
        "pg_rewind_completed",
        "old_primary_rejoined_as_standby",
        "rejoined_transaction_read_only",
        "receiver_streaming",
        "shared_system_identifier",
        "replay_lsn_verified",
        "acceptance_identity_preserved",
        "schedule_identity_preserved",
    }
    missing = sorted(key for key in required_winner_true if winner.get(key) is not True)
    if missing:
        raise RuntimeError(f"automatic-rejoin winner lacks evidence: {missing}")
    if winner.get("distributed_consensus_proven") is not False:
        raise RuntimeError("automatic-rejoin winner overclaims distributed consensus")
    if winner.get("partition_safe_fencing_proven") is not False:
        raise RuntimeError("automatic-rejoin winner overclaims partition-safe fencing")
    if winner.get("production_stonith_proven") is not False:
        raise RuntimeError("automatic-rejoin winner overclaims production STONITH")
    if winner.get("acceptance_count") != 1 or winner.get("replacement_count") != 1:
        raise RuntimeError("automatic-rejoin winner lifecycle counts drifted")

    if follower.get("automatic_rejoin_orchestration") is not True:
        raise RuntimeError("automatic-rejoin follower lacks orchestration evidence")
    if follower.get("topology_mutation_performed") is not False:
        raise RuntimeError("automatic-rejoin follower performed topology mutation")
    if follower.get("rewind_performed") is not False:
        raise RuntimeError("automatic-rejoin follower performed rewind")
    if follower.get("verification_performed") is not False:
        raise RuntimeError("automatic-rejoin follower performed verification")
    follower_contended = follower.get("lease_contended") is True
    follower_observed_completed = follower.get("already_rejoined") is True
    if follower_contended == follower_observed_completed:
        raise RuntimeError(
            "automatic-rejoin follower must prove exactly one no-op path: "
            f"{follower!r}"
        )

    if witness.get("status") != "rejoined":
        raise RuntimeError(f"automatic-rejoin witness did not complete: {witness!r}")
    if witness.get("rejoin_epoch") != 1:
        raise RuntimeError(f"automatic-rejoin epoch drifted: {witness!r}")
    if witness.get("winner_controller_id") != winner.get("controller_id"):
        raise RuntimeError("automatic-rejoin witness winner identity drifted")
    if follower.get("winner_controller_id") != winner.get("controller_id"):
        raise RuntimeError("automatic-rejoin follower did not observe the winner")
    return winner, follower


def main() -> int:
    primary_container = _required_environment("FAILOVER_PRIMARY_CONTAINER")
    promoted_container = _required_environment("FAILOVER_STANDBY_CONTAINER")
    primary_volume = _required_environment("FAILOVER_PRIMARY_VOLUME")
    rejoin_container = _required_environment("FAILOVER_REJOIN_CONTAINER")
    promoted_database_url = _required_environment("FAILOVER_STANDBY_DATABASE_URL")
    verification_report = Path(_required_environment("FAILOVER_REJOIN_REPORT_PATH"))
    summary_path = Path(_required_environment("FAILOVER_AUTOMATIC_REJOIN_REPORT_PATH"))

    state_directory = summary_path.parent / "preparation-repair-automatic-rejoin-state"
    if state_directory.exists():
        shutil.rmtree(state_directory)
    ready_directory = state_directory / "ready"
    ready_directory.mkdir(parents=True, exist_ok=True)
    release_gate = state_directory / "release-gate.json"
    witness_path = state_directory / "witness.json"
    lease_path = state_directory / "witness.lock"
    controller_ids = [f"automatic-rejoin-controller-{index}" for index in range(CONTROLLER_COUNT)]
    report_paths = [
        state_directory / f"controller-{index}.json"
        for index in range(CONTROLLER_COUNT)
    ]

    for path in (verification_report, summary_path):
        path.unlink(missing_ok=True)

    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        f"{ROOT}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(ROOT)
    )
    processes: list[subprocess.Popen[str]] = []
    try:
        for controller_id, report_path in zip(controller_ids, report_paths, strict=True):
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "--controller-id",
                    controller_id,
                    "--primary-container",
                    primary_container,
                    "--promoted-container",
                    promoted_container,
                    "--primary-volume",
                    primary_volume,
                    "--rejoin-container",
                    rejoin_container,
                    "--promoted-database-url",
                    promoted_database_url,
                    "--ready-directory",
                    str(ready_directory),
                    "--release-gate",
                    str(release_gate),
                    "--witness",
                    str(witness_path),
                    "--lease",
                    str(lease_path),
                    "--report",
                    str(report_path),
                    "--verification-report",
                    str(verification_report),
                ],
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            processes.append(process)

        ready_reports = _wait_for_ready_files(
            ready_directory,
            controller_ids,
            processes,
        )
        if len({report.get("controller_id") for report in ready_reports}) != CONTROLLER_COUNT:
            raise RuntimeError("automatic-rejoin ready identities are not distinct")
        if not all(
            report.get("topology", {}).get("old_primary_container_absent") is True
            and report.get("topology", {}).get("promoted_primary_writable") is True
            and report.get("topology", {}).get("old_primary_volume_retained") is True
            and report.get("topology", {}).get("rejoin_container_absent") is True
            for report in ready_reports
        ):
            raise RuntimeError(f"automatic-rejoin ready topology drifted: {ready_reports!r}")

        _write_json_atomically(
            release_gate,
            {
                "controller_count": CONTROLLER_COUNT,
                "released": True,
            },
        )

        for controller_id, process in zip(controller_ids, processes, strict=True):
            _collect_process(process, controller_id=controller_id)

        reports = [_read_json(path) for path in report_paths]
        witness = _read_json(witness_path)
        winner, follower = _validate_controller_reports(reports, witness)
        follower_contended = follower.get("lease_contended") is True
        follower_observed_completed = follower.get("already_rejoined") is True
        verification = _read_json(verification_report)
        if verification.get("valid") is not True:
            raise RuntimeError("automatic-rejoin underlying verification report is invalid")
        if verification.get("automatic_rejoin_orchestration") is not False:
            raise RuntimeError("underlying verifier must remain orchestration-neutral")

        _write_json_atomically(
            summary_path,
            {
                "valid": True,
                "postgresql_major": 16,
                "controller_count": CONTROLLER_COUNT,
                "controllers_ready_before_release": CONTROLLER_COUNT,
                "distinct_controller_identities": True,
                "single_local_rejoin_lease": True,
                "lease_winner_count": 1,
                "lease_follower_count": 1,
                "rejoin_epoch": 1,
                "automatic_rejoin_orchestration": True,
                "old_primary_container_absent_before_rejoin": True,
                "old_primary_volume_retained_before_rejoin": True,
                "promoted_primary_writable_before_rejoin": True,
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
                "acceptance_count": 1,
                "replacement_count": 1,
                "follower_topology_mutation_performed": False,
                "follower_lease_contended": follower_contended,
                "follower_observed_completed_witness": follower_observed_completed,
                "winner_controller_id": winner["controller_id"],
                "follower_controller_id": follower["controller_id"],
                "distributed_consensus_proven": False,
                "partition_safe_fencing_proven": False,
                "production_stonith_proven": False,
                "cross_host_lease_proven": False,
                "missing_wal_fallback_proven": False,
                "base_backup_fallback_proven": False,
                "representative_recovery_time_proven": False,
                "hosted_green_claim": False,
            },
        )
        return 0
    finally:
        for process in processes:
            _ensure_process_stopped(process)


if __name__ == "__main__":
    raise SystemExit(main())
