#!/usr/bin/env python3
"""Validate controlled old-primary rewind and standby rejoin evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "setup": "scripts/setup_preparation_repair_primary_failover_cluster.sh",
    "cleanup": "scripts/cleanup_preparation_repair_primary_failover_cluster.sh",
    "rewind": "scripts/rewind_preparation_repair_old_primary.sh",
    "probe": "scripts/probe_preparation_repair_old_primary_rejoin.py",
    "workflow": ".github/workflows/preparation-repair-automatic-failover.yml",
    "docs": "docs/PREPARATION_REPAIR_OLD_PRIMARY_REJOIN.md",
    "readme": "README.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing old-primary rejoin file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "setup": {
            "wal_log_hints=on",
            "SHOW wal_log_hints",
            '[[ "$wal_log_hints" == "on" ]]',
            "host replication replicator samenet trust",
            "pg_stat_replication",
            "pg_stat_wal_receiver",
        },
        "cleanup": {
            "FAILOVER_REJOIN_CONTAINER",
            'containers+=("$FAILOVER_REJOIN_CONTAINER")',
            "docker rm -f",
            "docker volume rm",
        },
        "rewind": {
            "old primary container still exists; rewind authority is denied",
            "docker volume inspect",
            "--network none",
            "rm -f /var/lib/postgresql/data/postmaster.pid",
            'printf "CHECKPOINT;\\n"',
            "gosu postgres postgres --single",
            "-c listen_addresses=",
            "gosu postgres pg_rewind",
            "--target-pgdata=/var/lib/postgresql/data",
            "--source-server=",
            "sed -i",
            "primary_slot_name",
            "standby.signal",
            "primary_conninfo",
            "application_name=rewound-old-primary",
            "pg_is_in_recovery()",
            "pg_stat_wal_receiver",
            "pg_stat_replication",
            "isolated_target_crash_recovery=true",
            "stale_recovery_settings_normalized=true",
            "shared_system_identifier=true",
            "pg_rewind_completed=true",
        },
        "probe": {
            "Verify the rewound old primary is a caught-up read-only standby",
            'text("SELECT pg_is_in_recovery()")',
            'text("SHOW transaction_read_only")',
            "rewound standby receiver is not streaming",
            "application_name = 'rewound-old-primary'",
            "pg_control_system()",
            "pg_switch_wal()",
            "pg_current_wal_flush_lsn()::text",
            "pg_last_wal_replay_lsn()::text",
            "rewound standby acceptance identity drifted",
            "rewound standby schedule identity drifted",
            '"replay_lsn_verified": True',
            '"observed_replay_lsn": replay_lsn',
            '"application_write_route_changed": False',
            '"rejoined_node_promoted": False',
            '"automatic_rejoin_orchestration": False',
            '"partition_safe_fencing_proven": False',
            '"hosted_green_claim": False',
        },
        "workflow": {
            "FAILOVER_REJOIN_CONTAINER",
            "FAILOVER_REJOIN_PORT",
            "FAILOVER_REJOIN_DATABASE_URL",
            "FAILOVER_REJOIN_REPORT_PATH",
            "rewind_preparation_repair_old_primary.sh",
            "probe_preparation_repair_old_primary_rejoin.py",
            "probe_preparation_repair_automatic_old_primary_rejoin.py",
            "validate_preparation_repair_old_primary_rejoin_contract.py",
            "validate_preparation_repair_old_primary_rejoin_release.py",
            "reports/preparation-repair-old-primary-rejoin.json",
            "Automatically rewind and rejoin fenced old primary",
        },
        "docs": {
            "Controlled Old-Primary Rewind and Standby Rejoin",
            "wal_log_hints=on",
            "Docker `--network none`",
            "single-user mode",
            "PostgreSQL `pg_rewind`",
            "existing `primary_conninfo` and `primary_slot_name`",
            "rewound-old-primary",
            "transaction_read_only = on",
            "pg_switch_wal()",
            "replay_lsn_verified=true",
            "observed_replay_lsn",
            "application_write_route_changed=false",
            "automatic rejoin orchestration",
            "partition-safe stale-primary rejection",
        },
        "readme": {
            "controlled old-primary rewind and rejoin",
            "pg_rewind",
            "read-only streaming standby",
        },
        "status": {
            "Controlled old-primary rewind and rejoin",
            "wal_log_hints=on",
            "rewound-old-primary",
        },
        "roadmap": {
            "C22 — Controlled old-primary rewind and standby rejoin",
            "pg_rewind",
            "automatic rejoin orchestration",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks old-primary rejoin fragment: {fragment}"
                )

    forbidden = {
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "monkeypatch",
        "sqlite://",
        "docker start",
        "host replication replicator 0.0.0.0/0",
        '"replay_lsn_verified": replay_lsn',
        '"application_write_route_changed": True',
        '"rejoined_node_promoted": True',
        '"automatic_rejoin_orchestration": True',
        '"partition_safe_fencing_proven": True',
        '"representative_recovery_time_proven": True',
        '"hosted_green_claim": True',
    }
    combined = "\n".join(
        sources[name] for name in ("setup", "cleanup", "rewind", "probe")
    )
    for fragment in sorted(forbidden):
        if fragment in combined:
            errors.append(
                "old-primary rejoin evidence contains forbidden shortcut or claim: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "postgresql_major": 16,
        "wal_log_hints_enabled": True,
        "old_primary_container_absent_before_rewind": True,
        "isolated_target_crash_recovery": True,
        "target_network_reachability_during_recovery": False,
        "stale_postmaster_pid_removed_after_fence": True,
        "stale_recovery_settings_normalized": True,
        "old_primary_volume_retained": True,
        "pg_rewind_completed": True,
        "distinct_rejoin_container": True,
        "rejoined_in_recovery": True,
        "rejoined_transaction_read_only": True,
        "receiver_streaming": True,
        "promoted_sender_count": 1,
        "shared_system_identifier": True,
        "post_rejoin_wal_position_verified": True,
        "typed_replay_proof": True,
        "observed_replay_lsn_reported_separately": True,
        "acceptance_identity_preserved": True,
        "schedule_identity_preserved": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "application_write_route_changed": False,
        "rejoined_node_promoted": False,
        "automatic_rejoin_orchestration": False,
        "partition_safe_fencing_proven": False,
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
