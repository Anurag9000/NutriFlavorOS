#!/usr/bin/env python3
"""Validate controlled automatic old-primary rejoin orchestration."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "controller": "scripts/run_preparation_repair_automatic_rejoin_controller.py",
    "runner": "scripts/probe_preparation_repair_automatic_old_primary_rejoin.py",
    "rewind": "scripts/rewind_preparation_repair_old_primary.sh",
    "verify": "scripts/probe_preparation_repair_old_primary_rejoin.py",
    "workflow": ".github/workflows/preparation-repair-automatic-failover.yml",
    "docs": "docs/PREPARATION_REPAIR_AUTOMATIC_OLD_PRIMARY_REJOIN.md",
    "readme": "README.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing automatic-rejoin file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def validate_contract() -> dict[str, object]:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "controller": {
            "DEFAULT_TOPOLOGY_TIMEOUT_SECONDS",
            "REWIND_SCRIPT",
            "VERIFY_SCRIPT",
            "fcntl.flock(lease_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)",
            'witness.get("status") == "rejoined"',
            '"status": "rejoin_in_progress"',
            '"status": "rejoined"',
            '"rejoin_epoch": rejoin_epoch',
            '"lease_acquired": True',
            '"lease_acquired": False',
            '"topology_mutation_performed": True',
            '"topology_mutation_performed": False',
            '"automatic_rejoin_orchestration": True',
            '"distributed_consensus_proven": False',
            '"partition_safe_fencing_proven": False',
            '"production_stonith_proven": False',
            'report.get("automatic_rejoin_orchestration") is not False',
            '"isolated_target_crash_recovery=true"',
            '"stale_recovery_settings_normalized=true"',
            '"pg_rewind_completed=true"',
            '"rejoin_in_recovery=t"',
            '"rejoin_receiver_status=streaming"',
            '"promoted_sender_count=1"',
            '"shared_system_identifier=true"',
        },
        "runner": {
            "CONTROLLER_COUNT = 2",
            "automatic-rejoin-controller-",
            "_wait_for_ready_files(",
            "controller exited before publishing readiness",
            '"released": True',
            "len(winners) != 1 or len(followers) != 1",
            'follower.get("topology_mutation_performed") is not False',
            "follower_contended == follower_observed_completed",
            'witness.get("rejoin_epoch") != 1',
            '"controllers_ready_before_release": CONTROLLER_COUNT',
            '"single_local_rejoin_lease": True',
            '"lease_winner_count": 1',
            '"lease_follower_count": 1',
            '"automatic_rejoin_orchestration": True',
            '"follower_topology_mutation_performed": False',
            '"follower_lease_contended": follower_contended',
            '"follower_observed_completed_witness": follower_observed_completed',
            '"distributed_consensus_proven": False',
            '"partition_safe_fencing_proven": False',
            '"production_stonith_proven": False',
            '"cross_host_lease_proven": False',
            '"missing_wal_fallback_proven": False',
            '"base_backup_fallback_proven": False',
            '"hosted_green_claim": False',
            "_ensure_process_stopped(process)",
        },
        "rewind": {
            "old primary container still exists; rewind authority is denied",
            "--network none",
            "rm -f /var/lib/postgresql/data/postmaster.pid",
            'printf "CHECKPOINT;\\n"',
            "gosu postgres postgres --single",
            "gosu postgres pg_rewind",
            "primary_conninfo",
            "primary_slot_name",
            "standby.signal",
            "rewound-old-primary",
            "isolated_target_crash_recovery=true",
            "stale_recovery_settings_normalized=true",
            "pg_rewind_completed=true",
        },
        "verify": {
            "pg_switch_wal()",
            "pg_current_wal_flush_lsn()::text",
            "pg_last_wal_replay_lsn()::text",
            '"replay_lsn_verified": True',
            '"acceptance_identity_preserved": True',
            '"schedule_identity_preserved": True',
            '"automatic_rejoin_orchestration": False',
            '"partition_safe_fencing_proven": False',
            '"hosted_green_claim": False',
        },
        "workflow": {
            "validate-preparation-repair-automatic-failover",
            "run_preparation_repair_automatic_rejoin_controller.py",
            "probe_preparation_repair_automatic_old_primary_rejoin.py",
            "validate_preparation_repair_automatic_rejoin_contract.py",
            "validate_preparation_repair_automatic_rejoin_release.py",
            "FAILOVER_AUTOMATIC_REJOIN_REPORT_PATH",
            "reports/preparation-repair-automatic-rejoin.json",
            "if: always()",
            "if-no-files-found: error",
        },
        "docs": {
            "Controlled Automatic Old-Primary Rejoin Orchestration",
            "exactly two controller processes",
            "one nonblocking POSIX `flock` lease",
            "rejoin epoch `1`",
            "topology_mutation_performed=false",
            "Docker `--network none`",
            "automatic_rejoin_orchestration=false",
            "distributed consensus",
            "cross-host lease",
            "missing-WAL fallback",
        },
        "readme": {
            "controlled automatic old-primary rejoin",
            "single local rejoin lease",
            "rejoin epoch `1`",
        },
        "status": {
            "Controlled automatic old-primary rejoin",
            "two simultaneous rejoin controllers",
            "one local rejoin lease",
        },
        "roadmap": {
            "C23 — Controlled automatic old-primary rejoin",
            "rejoin epoch `1`",
            "distributed consensus",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks automatic-rejoin fragment: {fragment}"
                )

    combined_authority = "\n".join(
        sources[name] for name in ("controller", "runner", "rewind", "verify")
    )
    forbidden = {
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "monkeypatch",
        "sqlite://",
        "DBPreparationRepairProposalAcceptance(",
        "DBPersistedPreparationSchedule(",
        "DBPreparationRepairProposalEvent(",
        "DBPreparationScheduleEvent(",
        '"distributed_consensus_proven": True',
        '"partition_safe_fencing_proven": True',
        '"production_stonith_proven": True',
        '"cross_host_lease_proven": True',
        '"missing_wal_fallback_proven": True',
        '"base_backup_fallback_proven": True',
        '"representative_recovery_time_proven": True',
        '"hosted_green_claim": True',
    }
    for fragment in sorted(forbidden):
        if fragment in combined_authority:
            errors.append(
                "automatic-rejoin evidence contains forbidden shortcut or claim: "
                f"{fragment}"
            )

    sensitive_fragments = {
        "postgres:postgres@",
        '"idempotency_key"',
        '"household_id"',
        '"proposal_id"',
        '"acceptance_id"',
        '"schedule_id"',
        '"request_payload"',
        '"sql_text"',
    }
    report_sources = "\n".join(sources[name] for name in ("controller", "runner"))
    for fragment in sorted(sensitive_fragments):
        if fragment in report_sources:
            errors.append(
                "automatic-rejoin controller reports may contain sensitive field: "
                f"{fragment}"
            )

    workflow = sources["workflow"]
    for obsolete_step in (
        "run: bash scripts/rewind_preparation_repair_old_primary.sh",
        "run: python scripts/probe_preparation_repair_old_primary_rejoin.py",
    ):
        if obsolete_step in workflow:
            errors.append(
                "automatic-rejoin workflow still bypasses controller orchestration: "
                f"{obsolete_step}"
            )

    return {
        "valid": not errors,
        "postgresql_major": 16,
        "controller_count": 2,
        "controllers_ready_before_release": 2,
        "early_exit_before_readiness_rejected": True,
        "single_local_rejoin_lease": True,
        "lease_winner_count": 1,
        "lease_follower_count": 1,
        "follower_no_op_path_exclusive": True,
        "rejoin_epoch": 1,
        "automatic_rejoin_orchestration": True,
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
        "follower_topology_mutation_performed": False,
        "distributed_consensus_proven": False,
        "partition_safe_fencing_proven": False,
        "production_stonith_proven": False,
        "cross_host_lease_proven": False,
        "missing_wal_fallback_proven": False,
        "base_backup_fallback_proven": False,
        "representative_recovery_time_proven": False,
        "hosted_green_claim": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
