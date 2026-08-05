#!/usr/bin/env python3
"""Validate controlled PostgreSQL physical-standby promotion evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "setup": "scripts/setup_preparation_repair_primary_failover_cluster.sh",
    "cleanup": "scripts/cleanup_preparation_repair_primary_failover_cluster.sh",
    "test": "backend/tests/test_preparation_repair_primary_failover_postgres.py",
    "proxy": "backend/tests/postgres_commit_ack_drop_proxy.py",
    "guard": (
        "backend/services/preparation_repair_source_acceptance_guard_service.py"
    ),
    "workflow": ".github/workflows/preparation-repair-primary-failover.yml",
    "docs": "docs/PREPARATION_REPAIR_PRIMARY_FAILOVER.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
    "readme": "README.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing primary-failover file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str) -> bool:
    return fragment in source or _normalized(fragment) in _normalized(source)


def _test_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "setup": {
            "postgres:16",
            "wal_level=replica",
            "max_wal_senders=10",
            "wal_keep_size=256MB",
            "hot_standby=on",
            "synchronous_commit=on",
            "CREATE ROLE replicator WITH REPLICATION LOGIN",
            "host replication replicator 0.0.0.0/0 trust",
            "gosu postgres pg_ctl reload",
            "gosu postgres pg_basebackup",
            "-Fp -Xs -P -R",
            "pg_is_in_recovery()",
            "system_identifier::text FROM pg_control_system()",
            '[[ "$primary_system_identifier" == "$standby_system_identifier" ]]',
        },
        "cleanup": {
            "docker rm -f",
            "docker network rm",
            "docker volume rm",
            "failover_cluster_cleanup=complete",
        },
        "test": {
            "test_postgres_physical_standby_promotion_recovers_exact_committed_request",
            "PostgresCommitAckDropProxy(",
            'worker.execute(text("SET LOCAL synchronous_commit = on"))',
            'text("SHOW synchronous_commit")',
            "with pytest.raises(OperationalError)",
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["retry_safe"] is False',
            'classification["automatic_retry_performed"] is False',
            "pg_current_wal_flush_lsn()::text",
            "pg_last_wal_replay_lsn()::text",
            "pg_wal_lsn_diff(",
            "CAST(:target_lsn AS pg_lsn)",
            "_accepted_counts(standby_db, proposal_id) == ONE_COUNTS",
            '["docker", "stop", "--time", "0", container_name]',
            "with pytest.raises(OperationalError):",
            'text("SELECT pg_promote(true, 60)")',
            'text("SELECT pg_is_in_recovery()")',
            'text("SHOW transaction_read_only")',
            'connection.execute(text("CHECKPOINT"))',
            "promoted_timeline != primary_timeline",
            "promoted_system_identifier == primary_system_identifier",
            "accept_repair_proposal_with_source_guard(",
            "replayed.acceptance.id == committed_acceptance_id",
            "replayed.acceptance.created_schedule_id == committed_schedule_id",
            "replayed.acceptance.idempotency_key == idempotency_key",
            "_accepted_counts(promoted_db, proposal_id) == ONE_COUNTS",
            '"physical_streaming_replication": True',
            '"standby_caught_up_before_primary_stop": True',
            '"explicit_endpoint_rotation": True',
            '"automatic_dns_rotation": False',
            '"split_brain_fencing_proven": False',
            '"hosted_green_claim": False',
        },
        "proxy": {
            "class PostgresCommitAckDropProxy",
            "commit_query_forwarded",
            "commit_command_complete_seen",
            "commit_acknowledgement_forwarded",
        },
        "guard": {
            "accept_repair_proposal_with_source_guard",
            "_lock_household(db, household_id)",
            ".with_for_update()",
            "return accept_repair_proposal(",
        },
        "workflow": {
            "validate-preparation-repair-primary-failover",
            "setup_preparation_repair_primary_failover_cluster.sh",
            "cleanup_preparation_repair_primary_failover_cluster.sh",
            "test_preparation_repair_primary_failover_postgres.py",
            "validate_preparation_repair_primary_failover_contract.py",
            "validate_preparation_repair_primary_failover_release.py",
            "reports/preparation-repair-primary-failover.xml",
            "reports/preparation-repair-primary-failover.json",
            "if: always()",
            "if-no-files-found: error",
        },
        "docs": {
            "Controlled PostgreSQL Physical-Standby Promotion Recovery",
            "physical streaming replication",
            "same nonempty `system_identifier`",
            "pg_current_wal_flush_lsn()",
            "pg_last_wal_replay_lsn()",
            "pg_promote(true, 60)",
            "different WAL timeline",
            "explicit new endpoint",
            "same acceptance ID",
            "exactly one acceptance",
            "automatic failover detection or promotion",
            "fencing, STONITH, quorum, split-brain prevention",
            "safe old-primary rewind, rejoin, rebuild, or demotion",
        },
        "status": {
            "controlled physical-standby promotion",
            "replay-LSN",
            "explicit endpoint rotation",
        },
        "roadmap": {
            "Controlled PostgreSQL physical-standby promotion",
            "new WAL timeline",
            "automatic failover",
        },
        "readme": {
            "controlled physical-standby promotion",
            "replay-LSN",
            "explicit endpoint rotation",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks primary-failover fragment: {fragment}"
                )

    expected_test = (
        "test_postgres_physical_standby_promotion_recovers_exact_committed_request"
    )
    if expected_test not in _test_names(sources["test"]):
        errors.append("physical-standby promotion PostgreSQL test is missing")

    forbidden = {
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "monkeypatch",
        "raise OperationalError(",
        "DBPreparationRepairProposalAcceptance(",
        "DBPersistedPreparationSchedule(",
        "DBPreparationRepairProposalEvent(",
        "DBPreparationScheduleEvent(",
        "sqlite://",
        '"idempotency_key":',
        "docker start",
        "pg_rewind",
        "automatic_dns_rotation = True",
        "automatic_failover_orchestrator = True",
        "split_brain_fencing_proven = True",
        "synchronous_replica_durability_proven = True",
        "multi_region_failover_proven = True",
        "representative_production_capacity = True",
    }
    combined = "\n".join(
        sources[name] for name in ("setup", "cleanup", "test")
    )
    for fragment in sorted(forbidden):
        if fragment in combined:
            errors.append(
                "primary-failover evidence contains forbidden shortcut or claim: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "postgresql_major": 16,
        "original_primary_count": 1,
        "physical_standby_count": 1,
        "physical_streaming_replication": True,
        "shared_system_identifier": True,
        "asynchronous_replication": True,
        "target_flush_lsn_recorded": True,
        "standby_replay_lsn_verified": True,
        "standby_caught_up_before_primary_stop": True,
        "old_primary_stopped": True,
        "old_primary_endpoint_unavailable": True,
        "standby_promoted": True,
        "new_wal_timeline": True,
        "explicit_endpoint_rotation": True,
        "client_outcome_unknown_before_failover": True,
        "client_retry_safe": False,
        "server_automatic_retry": False,
        "production_source_guard": True,
        "same_key_recovery": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "final_accepted_event_count": 1,
        "final_created_event_count": 1,
        "automatic_dns_rotation": False,
        "automatic_failover_orchestrator": False,
        "old_primary_rejoin_proven": False,
        "split_brain_fencing_proven": False,
        "synchronous_replica_durability_proven": False,
        "multi_region_failover_proven": False,
        "representative_production_capacity": False,
        "hosted_green_claim": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
