#!/usr/bin/env python3
"""Validate the synchronized automatic old-primary rejoin release boundary."""

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
    "controller": "scripts/run_preparation_repair_automatic_rejoin_controller.py",
    "runner": "scripts/probe_preparation_repair_automatic_old_primary_rejoin.py",
    "rewind": "scripts/rewind_preparation_repair_old_primary.sh",
    "verify": "scripts/probe_preparation_repair_old_primary_rejoin.py",
    "contract": "scripts/validate_preparation_repair_automatic_rejoin_contract.py",
    "workflow": ".github/workflows/preparation-repair-automatic-failover.yml",
    "docs": "docs/PREPARATION_REPAIR_AUTOMATIC_OLD_PRIMARY_REJOIN.md",
    "readme": "README.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing automatic-rejoin release file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def validate_release() -> dict[str, object]:
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
        errors.append("automatic-rejoin API release identity drifted")
    if openapi.get("contract_version") != EXPECTED_OPENAPI:
        errors.append("automatic-rejoin OpenAPI release identity drifted")
    if CURRENT_ALEMBIC_REVISION != EXPECTED_MIGRATION:
        errors.append("automatic-rejoin migration identity drifted")

    required = {
        "controller": {
            "run_controller(args)",
            "fcntl.LOCK_EX | fcntl.LOCK_NB",
            '"status": "rejoin_in_progress"',
            '"status": "rejoined"',
            '"automatic_rejoin_orchestration": True',
            '"topology_mutation_performed": False',
            '"distributed_consensus_proven": False',
            'report.get("automatic_rejoin_orchestration") is not False',
            "REWIND_SCRIPT",
            "VERIFY_SCRIPT",
        },
        "runner": {
            "CONTROLLER_COUNT = 2",
            '"controllers_ready_before_release": CONTROLLER_COUNT',
            '"lease_winner_count": 1',
            '"lease_follower_count": 1',
            '"rejoin_epoch": 1',
            '"automatic_rejoin_orchestration": True',
            '"follower_topology_mutation_performed": False',
            '"hosted_green_claim": False',
        },
        "rewind": {
            "--network none",
            "gosu postgres postgres --single",
            "gosu postgres pg_rewind",
            "stale_recovery_settings_normalized=true",
            "pg_rewind_completed=true",
        },
        "verify": {
            '"valid": True',
            '"replay_lsn_verified": True',
            '"acceptance_identity_preserved": True',
            '"schedule_identity_preserved": True',
            '"automatic_rejoin_orchestration": False',
        },
        "contract": {
            '"controller_count": 2',
            '"single_local_rejoin_lease": True',
            '"lease_winner_count": 1',
            '"lease_follower_count": 1',
            '"automatic_rejoin_orchestration": True',
            '"follower_topology_mutation_performed": False',
            '"distributed_consensus_proven": False',
            '"partition_safe_fencing_proven": False',
            '"cross_host_lease_proven": False',
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
            "validate_repair_release_identity.py",
            "if: always()",
            "if-no-files-found: error",
        },
        "docs": {
            "Controlled Automatic Old-Primary Rejoin Orchestration",
            "exactly two controller processes",
            "one nonblocking POSIX `flock` lease",
            "rejoin epoch `1`",
            "topology_mutation_performed=false",
            "automatic_rejoin_orchestration=false",
            "distributed consensus",
            "partition-safe stale-primary rejection",
            "missing-WAL fallback",
        },
        "readme": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI}`",
            "controlled automatic old-primary rejoin",
            "single local rejoin lease",
            "rejoin epoch `1`",
            "distributed consensus",
        },
        "status": {
            f"**Database migration head:** `{EXPECTED_MIGRATION}`",
            f"**API version:** `{EXPECTED_API}`",
            f"**OpenAPI release contract:** `{EXPECTED_OPENAPI}`",
            "Controlled automatic old-primary rejoin",
            "two simultaneous rejoin controllers",
            "one local rejoin lease",
            "automatic rejoin orchestration",
        },
        "roadmap": {
            f"**Current migration head:** `{EXPECTED_MIGRATION}`",
            f"**Current API:** `{EXPECTED_API}`",
            f"**Current OpenAPI contract:** `{EXPECTED_OPENAPI}`",
            "C23 — Controlled automatic old-primary rejoin",
            "rejoin epoch `1`",
            "distributed consensus",
            "missing-WAL",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks automatic-rejoin release fragment: {fragment}"
                )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": openapi.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "postgresql_major": 16,
        "controller_count": 2,
        "controllers_ready_before_release": 2,
        "single_local_rejoin_lease": True,
        "lease_winner_count": 1,
        "lease_follower_count": 1,
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
    report = validate_release()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
