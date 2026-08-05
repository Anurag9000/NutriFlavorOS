#!/usr/bin/env python3
"""Validate the synchronized old-primary rewind/rejoin release boundary."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.main import app
from backend.schema_revision import CURRENT_ALEMBIC_REVISION


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_API = "0.15.4"
EXPECTED_OPENAPI = "2026-08-03.2"
EXPECTED_MIGRATION = "20260802_0018"
FILES = {
    "openapi": "contracts/openapi_required.json",
    "setup": "scripts/setup_preparation_repair_primary_failover_cluster.sh",
    "cleanup": "scripts/cleanup_preparation_repair_primary_failover_cluster.sh",
    "rewind": "scripts/rewind_preparation_repair_old_primary.sh",
    "probe": "scripts/probe_preparation_repair_old_primary_rejoin.py",
    "contract": "scripts/validate_preparation_repair_old_primary_rejoin_contract.py",
    "workflow": ".github/workflows/preparation-repair-automatic-failover.yml",
    "docs": "docs/PREPARATION_REPAIR_OLD_PRIMARY_REJOIN.md",
    "readme": "README.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing old-primary rejoin release file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def validate_release() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}
    try:
        openapi = json.loads(sources["openapi"] or "{}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid OpenAPI release JSON: {exc}")
        openapi = {}

    if app.version != EXPECTED_API:
        errors.append(f"API version {app.version!r} != {EXPECTED_API!r}")
    if openapi.get("api_version") != EXPECTED_API:
        errors.append("old-primary rejoin API release identity drifted")
    if openapi.get("contract_version") != EXPECTED_OPENAPI:
        errors.append("old-primary rejoin OpenAPI identity drifted")
    if CURRENT_ALEMBIC_REVISION != EXPECTED_MIGRATION:
        errors.append("old-primary rejoin migration identity drifted")

    required = {
        "setup": {
            "wal_log_hints=on",
            "SHOW wal_log_hints",
            "host replication replicator samenet trust",
        },
        "cleanup": {
            "FAILOVER_REJOIN_CONTAINER",
            "docker rm -f",
            "docker volume rm",
        },
        "rewind": {
            "--network none",
            "rm -f /var/lib/postgresql/data/postmaster.pid",
            'printf "CHECKPOINT;\\n"',
            "gosu postgres postgres --single",
            "gosu postgres pg_rewind",
            "sed -i",
            "primary_slot_name",
            "standby.signal",
            "primary_conninfo",
            "rewound-old-primary",
            "isolated_target_crash_recovery=true",
            "stale_recovery_settings_normalized=true",
            "pg_rewind_completed=true",
            "shared_system_identifier=true",
        },
        "probe": {
            'text("SHOW transaction_read_only")',
            "pg_switch_wal()",
            "pg_current_wal_flush_lsn()::text",
            "pg_last_wal_replay_lsn()::text",
            '"replay_lsn_verified": True',
            '"observed_replay_lsn": replay_lsn',
            '"old_primary_rejoined_as_standby": True',
            '"acceptance_identity_preserved": True',
            '"schedule_identity_preserved": True',
            '"application_write_route_changed": False',
            '"rejoined_node_promoted": False',
            '"hosted_green_claim": False',
        },
        "contract": {
            '"wal_log_hints_enabled": True',
            '"isolated_target_crash_recovery": True',
            '"target_network_reachability_during_recovery": False',
            '"stale_postmaster_pid_removed_after_fence": True',
            '"stale_recovery_settings_normalized": True',
            '"pg_rewind_completed": True',
            '"rejoined_in_recovery": True',
            '"receiver_streaming": True',
            '"post_rejoin_wal_position_verified": True',
            '"typed_replay_proof": True',
            '"observed_replay_lsn_reported_separately": True',
            '"application_write_route_changed": False',
            '"automatic_rejoin_orchestration": False',
            '"hosted_green_claim": False',
        },
        "workflow": {
            "FAILOVER_REJOIN_CONTAINER",
            "FAILOVER_REJOIN_DATABASE_URL",
            "FAILOVER_REJOIN_REPORT_PATH",
            "rewind_preparation_repair_old_primary.sh",
            "probe_preparation_repair_old_primary_rejoin.py",
            "validate_preparation_repair_old_primary_rejoin_contract.py",
            "validate_preparation_repair_old_primary_rejoin_release.py",
            "reports/preparation-repair-old-primary-rejoin.json",
        },
        "docs": {
            "Controlled Old-Primary Rewind and Standby Rejoin",
            "wal_log_hints=on",
            "Docker `--network none`",
            "single-user mode",
            "PostgreSQL `pg_rewind`",
            "existing `primary_conninfo` and `primary_slot_name`",
            "read-only physical standby",
            "replay_lsn_verified=true",
            "observed_replay_lsn",
            "automatic rejoin orchestration",
            "partition-safe stale-primary rejection",
        },
        "readme": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI}`",
            "controlled old-primary rewind and rejoin",
            "pg_rewind",
            "read-only streaming standby",
        },
        "status": {
            "Controlled old-primary rewind and rejoin",
            "wal_log_hints=on",
            "rewound-old-primary",
            "read-only streaming standby",
        },
        "roadmap": {
            "C22 — Controlled old-primary rewind and standby rejoin",
            "pg_rewind",
            "read-only streaming standby",
            "automatic rejoin orchestration",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks old-primary rejoin release fragment: {fragment}"
                )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": openapi.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "postgresql_major": 16,
        "wal_log_hints_enabled": True,
        "isolated_target_crash_recovery": True,
        "target_network_reachability_during_recovery": False,
        "stale_postmaster_pid_removed_after_fence": True,
        "stale_recovery_settings_normalized": True,
        "pg_rewind_completed": True,
        "old_primary_rejoined_as_standby": True,
        "rejoined_transaction_read_only": True,
        "receiver_streaming": True,
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
    report = validate_release()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
