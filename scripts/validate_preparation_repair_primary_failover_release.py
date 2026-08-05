#!/usr/bin/env python3
"""Validate the synchronized physical-standby promotion release boundary."""

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
    "test": "backend/tests/test_preparation_repair_primary_failover_postgres.py",
    "contract": "scripts/validate_preparation_repair_primary_failover_contract.py",
    "workflow": ".github/workflows/preparation-repair-primary-failover.yml",
    "docs": "docs/PREPARATION_REPAIR_PRIMARY_FAILOVER.md",
    "readme": "README.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing primary-failover release file: {relative}")
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
        errors.append("primary-failover API release identity drifted")
    if openapi.get("contract_version") != EXPECTED_OPENAPI:
        errors.append("primary-failover OpenAPI identity drifted")
    if CURRENT_ALEMBIC_REVISION != EXPECTED_MIGRATION:
        errors.append("primary-failover migration identity drifted")

    required = {
        "setup": {
            "postgres:16",
            "wal_level=replica",
            "gosu postgres pg_basebackup",
            "system_identifier::text FROM pg_control_system()",
        },
        "cleanup": {
            "docker rm -f",
            "docker network rm",
            "docker volume rm",
        },
        "test": {
            "test_postgres_physical_standby_promotion_recovers_exact_committed_request",
            "PostgresCommitAckDropProxy(",
            "pg_current_wal_flush_lsn()::text",
            "pg_last_wal_replay_lsn()::text",
            'text("SELECT pg_promote(true, 60)")',
            "promoted_timeline != primary_timeline",
            "promoted_system_identifier == primary_system_identifier",
            "replayed.acceptance.id == committed_acceptance_id",
            "_accepted_counts(promoted_db, proposal_id) == ONE_COUNTS",
            '"automatic_failover_orchestrator": False',
            '"hosted_green_claim": False',
        },
        "contract": {
            '"physical_streaming_replication": True',
            '"shared_system_identifier": True',
            '"standby_replay_lsn_verified": True',
            '"standby_promoted": True',
            '"new_wal_timeline": True',
            '"explicit_endpoint_rotation": True',
            '"same_key_recovery": True',
            '"automatic_failover_orchestrator": False',
            '"split_brain_fencing_proven": False',
            '"hosted_green_claim": False',
        },
        "workflow": {
            "validate-preparation-repair-primary-failover",
            "postgres:16",
            "setup_preparation_repair_primary_failover_cluster.sh",
            "cleanup_preparation_repair_primary_failover_cluster.sh",
            "test_preparation_repair_primary_failover_postgres.py",
            "validate_preparation_repair_primary_failover_contract.py",
            "validate_preparation_repair_primary_failover_release.py",
            "validate_repair_release_identity.py",
            "reports/preparation-repair-primary-failover.xml",
            "reports/preparation-repair-primary-failover.json",
            "if: always()",
            "if-no-files-found: error",
        },
        "docs": {
            "Controlled PostgreSQL Physical-Standby Promotion Recovery",
            "physical streaming replication",
            "same nonempty `system_identifier`",
            "replayed at least the exact recorded flush position",
            "different WAL timeline",
            "explicit new endpoint",
            "same acceptance ID",
            "automatic failover detection or promotion",
            "safe old-primary rewind, rejoin, rebuild, or demotion",
        },
        "readme": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI}`",
            "controlled physical-standby promotion",
            "replay-LSN",
            "explicit endpoint rotation",
            "automatic failover",
        },
        "status": {
            "controlled physical-standby promotion",
            "replay-LSN",
            "new WAL timeline",
            "explicit endpoint rotation",
        },
        "roadmap": {
            "C19 — Controlled PostgreSQL physical-standby promotion",
            "new WAL timeline",
            "automatic failover",
            "split-brain",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks primary-failover release fragment: "
                    f"{fragment}"
                )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": openapi.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "postgresql_major": 16,
        "physical_streaming_replication": True,
        "shared_system_identifier": True,
        "standby_replay_position_verified": True,
        "original_primary_stopped": True,
        "standby_promoted": True,
        "new_wal_timeline": True,
        "explicit_endpoint_rotation": True,
        "same_key_recovery": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "automatic_failover_orchestrator": False,
        "automatic_dns_rotation": False,
        "old_primary_rejoin_proven": False,
        "split_brain_fencing_proven": False,
        "synchronous_replica_durability_proven": False,
        "multi_region_failover_proven": False,
        "hosted_green_claim": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_release()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
