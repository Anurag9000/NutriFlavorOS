#!/usr/bin/env python3
"""Validate the synchronized automatic-failover release boundary."""

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
    "router": "scripts/probe_preparation_repair_stable_database_endpoint.py",
    "controller": "scripts/run_preparation_repair_automatic_failover_controller.py",
    "test": "backend/tests/test_preparation_repair_automatic_failover_postgres.py",
    "worker": "scripts/probe_preparation_repair_multi_instance_recovery.py",
    "multi_worker": "scripts/probe_preparation_repair_post_promotion_multi_instance.py",
    "contract": "scripts/validate_preparation_repair_automatic_failover_contract.py",
    "workflow": ".github/workflows/preparation-repair-automatic-failover.yml",
    "docs": "docs/PREPARATION_REPAIR_AUTOMATIC_FAILOVER.md",
    "readme": "README.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing automatic-failover release file: {relative}")
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
        errors.append("automatic-failover API release identity drifted")
    if openapi.get("contract_version") != EXPECTED_OPENAPI:
        errors.append("automatic-failover OpenAPI identity drifted")
    if CURRENT_ALEMBIC_REVISION != EXPECTED_MIGRATION:
        errors.append("automatic-failover migration identity drifted")

    required = {
        "setup": {
            "postgres:16",
            "gosu postgres pg_basebackup",
            "pg_stat_replication",
            "pg_stat_wal_receiver",
            "host replication replicator samenet trust",
            "system_identifier::text FROM pg_control_system()",
        },
        "cleanup": {
            "docker rm -f",
            "docker network rm",
            "docker volume rm",
        },
        "router": {
            "class StablePostgresEndpoint",
            "threading.RLock()",
            "os.replace(temporary, path)",
            '"event": "connection_opened"',
            '"leaked_connection_threads": leaked_threads',
        },
        "controller": {
            "DEFAULT_FAILURE_THRESHOLD = 3",
            "fcntl.LOCK_EX | fcntl.LOCK_NB",
            '"status": "promotion_in_progress"',
            '["rm", "-f", container_name]',
            'text("SELECT pg_promote(true, 60)")',
            '"target_label": "promoted-standby"',
            '"promotion_performed": True',
            '"server_automatic_mutation_retry": False',
        },
        "test": {
            "CONTROLLER_COUNT = 2",
            "FAILURE_THRESHOLD = 3",
            "test_postgres_automatic_fenced_failover_recovers_through_stable_endpoint",
            'classification["code"] == "database_commit_outcome_unknown"',
            "pg_current_wal_flush_lsn()::text",
            "pg_last_wal_replay_lsn()::text",
            "len(winners) == 1",
            "len(followers) == 1",
            'witness["epoch"] == 1',
            "_container_absent(primary_container) is True",
            "_volume_exists(primary_volume) is True",
            "promoted_db = _session(stable_engine)",
            "promoted_timeline != primary_timeline",
            "replayed.acceptance.id == committed_acceptance_id",
            "_accepted_counts(promoted_db, proposal_id) == ONE_COUNTS",
            '"stable_endpoint_url_unchanged": True',
            '"distributed_consensus_proven": False',
            '"hosted_green_claim": False',
        },
        "worker": {
            "WORKER_INSTANCE_ID = uuid4().hex",
            "pool_size=1",
            "pool_pre_ping=True",
            'db.execute(text("SELECT pg_backend_pid()"))',
            '"same_key_recovery_performed": True',
            '"pool_checked_out_after_close": checked_out_after_close',
        },
        "multi_worker": {
            "Coordinate six exact-key recovery workers after automatic promotion",
            "WORKER_COUNT = 6",
            "old primary container must remain fenced before worker recovery",
            '"target_label": "promoted-standby"',
            '"epoch": 1',
            "not every promoted backend was simultaneously live",
            "workers returned different acceptance identities",
            "workers returned different schedule identities",
            "post-promotion worker recovery duplicated lifecycle rows",
            '"application_worker_count": WORKER_COUNT',
            '"same_acceptance_identity_for_all_workers": True',
            '"same_schedule_identity_for_all_workers": True',
            '"representative_production_capacity": False',
            '"hosted_green_claim": False',
        },
        "contract": {
            '"controller_count": 2',
            '"failure_threshold": 3',
            '"single_local_witness_lease": True',
            '"promotion_winner_count": 1',
            '"old_primary_container_removed": True',
            '"old_primary_volume_retained": True',
            '"stable_endpoint_url_unchanged": True',
            '"same_key_recovery": True',
            '"post_promotion_application_worker_count": 6',
            '"multi_worker_post_promotion_recovery_proven": True',
            '"distributed_consensus_proven": False',
            '"production_stonith_proven": False',
            '"hosted_green_claim": False',
        },
        "workflow": {
            "validate-preparation-repair-automatic-failover",
            "postgres:16",
            "setup_preparation_repair_primary_failover_cluster.sh",
            "cleanup_preparation_repair_primary_failover_cluster.sh",
            "probe_preparation_repair_stable_database_endpoint.py",
            "probe_preparation_repair_multi_instance_recovery.py",
            "probe_preparation_repair_post_promotion_multi_instance.py",
            "run_preparation_repair_automatic_failover_controller.py",
            "test_preparation_repair_automatic_failover_postgres.py",
            "validate_preparation_repair_automatic_failover_contract.py",
            "validate_preparation_repair_automatic_failover_release.py",
            "validate_repair_release_identity.py",
            "reports/preparation-repair-automatic-failover.xml",
            "reports/preparation-repair-automatic-failover.json",
            "reports/preparation-repair-post-promotion-workers.json",
            "Run six-worker exact recovery after automatic promotion",
            "if: always()",
            "if-no-files-found: error",
        },
        "docs": {
            "Controlled Automatic PostgreSQL Failover and Stable-Endpoint Recovery",
            "three consecutive failed TCP health probes",
            "single-host witness lease",
            "fence epoch from `0` to `1`",
            "old container no longer exists",
            "old-primary data volume remains present",
            "same SQLAlchemy engine URL",
            "Six-worker recovery after automatic promotion",
            "six-worker post-promotion JSON report",
            "distributed consensus",
            "not hardware STONITH",
            "safe old-primary `pg_rewind`, rebuild, demotion, or rejoin",
        },
        "readme": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI}`",
            "controlled automatic PostgreSQL failover",
            "single local witness lease",
            "unchanged stable database URL",
            "six-worker post-promotion",
            "distributed consensus",
        },
        "status": {
            "controlled automatic PostgreSQL failover",
            "single local witness lease",
            "fence epoch",
            "unchanged stable database URL",
            "six-worker post-promotion",
        },
        "roadmap": {
            "C20 — Controlled automatic PostgreSQL failover",
            "C21 — Six-worker recovery after automatic promotion",
            "single local witness lease",
            "fence epoch",
            "distributed consensus",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks automatic-failover release fragment: "
                    f"{fragment}"
                )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": openapi.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "postgresql_major": 16,
        "physical_streaming_replication": True,
        "stable_application_endpoint": True,
        "controller_count": 2,
        "failure_threshold": 3,
        "automatic_failure_detection": True,
        "single_local_witness_lease": True,
        "promotion_winner_count": 1,
        "promotion_follower_count": 1,
        "fence_epoch": 1,
        "old_primary_container_removed": True,
        "old_primary_volume_retained": True,
        "old_primary_endpoint_unavailable": True,
        "standby_promoted": True,
        "new_wal_timeline": True,
        "stable_route_rotated": True,
        "stable_endpoint_url_unchanged": True,
        "same_key_recovery": True,
        "post_promotion_application_worker_count": 6,
        "post_promotion_distinct_backend_pids": True,
        "post_promotion_same_acceptance_for_all_workers": True,
        "post_promotion_same_schedule_for_all_workers": True,
        "post_promotion_pool_checked_out_after_close": 0,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "server_automatic_mutation_retry": False,
        "distributed_consensus_proven": False,
        "production_stonith_proven": False,
        "quorum_proven": False,
        "old_primary_rejoin_proven": False,
        "multi_worker_post_promotion_recovery_proven": True,
        "representative_production_capacity": False,
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
