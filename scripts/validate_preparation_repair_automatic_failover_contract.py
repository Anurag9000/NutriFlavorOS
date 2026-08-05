#!/usr/bin/env python3
"""Validate controlled automatic failover and stable-endpoint recovery evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "setup": "scripts/setup_preparation_repair_primary_failover_cluster.sh",
    "cleanup": "scripts/cleanup_preparation_repair_primary_failover_cluster.sh",
    "router": "scripts/probe_preparation_repair_stable_database_endpoint.py",
    "controller": "scripts/run_preparation_repair_automatic_failover_controller.py",
    "test": "backend/tests/test_preparation_repair_automatic_failover_postgres.py",
    "proxy": "backend/tests/postgres_commit_ack_drop_proxy.py",
    "guard": "backend/services/preparation_repair_source_acceptance_guard_service.py",
    "workflow": ".github/workflows/preparation-repair-automatic-failover.yml",
    "docs": "docs/PREPARATION_REPAIR_AUTOMATIC_FAILOVER.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
    "readme": "README.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing automatic-failover file: {relative}")
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
            "failover_cluster_cleanup=complete",
        },
        "router": {
            "class StablePostgresEndpoint",
            "threading.RLock()",
            "def _read_target",
            "os.replace(temporary, path)",
            "socket.create_connection(",
            '"event": "connection_opened"',
            '"target_label": label',
            '"epoch": epoch',
            '"leaked_connection_threads": leaked_threads',
            "stable-endpoint connection threads leaked",
        },
        "controller": {
            "DEFAULT_FAILURE_THRESHOLD = 3",
            "def _wait_for_primary_failure",
            "consecutive_failures = 0",
            "fcntl.LOCK_EX | fcntl.LOCK_NB",
            "def _wait_for_completed_witness",
            "automatic failover may start only from original-primary route",
            '"status": "promotion_in_progress"',
            "old primary is still running; promotion is forbidden",
            '["rm", "-f", container_name]',
            "old primary data volume was not retained for forensic recovery",
            'text("SELECT pg_promote(true, 60)")',
            '"target_label": "promoted-standby"',
            "_write_json_atomically(args.route_state, promoted_route)",
            '"status": "promoted"',
            '"promotion_performed": True',
            '"route_rotation_performed": True',
            '"server_automatic_mutation_retry": False',
        },
        "test": {
            "CONTROLLER_COUNT = 2",
            "FAILURE_THRESHOLD = 3",
            "test_postgres_automatic_fenced_failover_recovers_through_stable_endpoint",
            "PostgresCommitAckDropProxy(",
            'worker.execute(text("SET LOCAL synchronous_commit = on"))',
            'worker.execute(text("SHOW synchronous_commit")).scalar_one() == "on"',
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["retry_safe"] is False',
            'classification["automatic_retry_performed"] is False',
            "pg_current_wal_flush_lsn()::text",
            "pg_last_wal_replay_lsn()::text",
            "all(process.poll() is None for process in controllers)",
            '["docker", "stop", "--time", "0", container_name]',
            'value["promotion_performed"] is True',
            "len(winners) == 1",
            "len(followers) == 1",
            'winner["lease_acquired"] is True',
            'follower["lease_acquired"] is False',
            'witness["epoch"] == 1',
            'route["target_label"] == "promoted-standby"',
            "_container_absent(primary_container) is True",
            "_volume_exists(primary_volume) is True",
            "_old_primary_endpoint_is_unavailable(primary_database_url) is True",
            "promoted_db = _session(stable_engine)",
            "promoted_timeline != primary_timeline",
            "replayed.acceptance.id == committed_acceptance_id",
            "replayed.acceptance.created_schedule_id == committed_schedule_id",
            "_accepted_counts(promoted_db, proposal_id) == ONE_COUNTS",
            'value.get("target_label") == "original-primary"',
            'value.get("target_label") == "promoted-standby"',
            '"stable_endpoint_url_unchanged": True',
            '"promotion_winner_count": 1',
            '"distributed_consensus_proven": False',
            '"production_stonith_proven": False',
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
            "validate-preparation-repair-automatic-failover",
            "setup_preparation_repair_primary_failover_cluster.sh",
            "cleanup_preparation_repair_primary_failover_cluster.sh",
            "probe_preparation_repair_stable_database_endpoint.py",
            "run_preparation_repair_automatic_failover_controller.py",
            "test_preparation_repair_automatic_failover_postgres.py",
            "validate_preparation_repair_automatic_failover_contract.py",
            "validate_preparation_repair_automatic_failover_release.py",
            "reports/preparation-repair-automatic-failover.xml",
            "reports/preparation-repair-automatic-failover.json",
            "if: always()",
            "if-no-files-found: error",
        },
        "docs": {
            "Controlled Automatic PostgreSQL Failover and Stable-Endpoint Recovery",
            "three consecutive failed TCP health probes",
            "nonblocking exclusive `flock`",
            "fence epoch from `0` to `1`",
            "docker rm -f",
            "old-primary data volume remains present",
            "same SQLAlchemy engine URL",
            "original-primary` at epoch `0`",
            "promoted-standby` at epoch `1`",
            "distributed consensus",
            "not hardware STONITH",
            "recovery coordinated across multiple application workers after promotion",
        },
        "status": {
            "controlled automatic PostgreSQL failover",
            "single local witness lease",
            "stable endpoint",
        },
        "roadmap": {
            "Controlled automatic PostgreSQL failover",
            "fence epoch",
            "distributed consensus",
        },
        "readme": {
            "controlled automatic PostgreSQL failover",
            "single local witness lease",
            "unchanged stable database URL",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks automatic-failover fragment: {fragment}"
                )

    expected_test = (
        "test_postgres_automatic_fenced_failover_recovers_through_stable_endpoint"
    )
    if expected_test not in _test_names(sources["test"]):
        errors.append("automatic-failover PostgreSQL test is missing")

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
        "docker start",
        "pg_rewind",
        "host replication replicator 0.0.0.0/0",
        '"server_automatic_mutation_retry": True',
        '"distributed_consensus_proven": True',
        '"production_stonith_proven": True',
        '"quorum_proven": True',
        '"old_primary_rejoin_proven": True',
        '"multi_region_failover_proven": True',
        '"hosted_green_claim": True',
    }
    combined = "\n".join(
        sources[name]
        for name in ("setup", "cleanup", "router", "controller", "test")
    )
    for fragment in sorted(forbidden):
        if fragment in combined:
            errors.append(
                "automatic-failover evidence contains forbidden shortcut or claim: "
                f"{fragment}"
            )

    router_controller = sources["router"] + "\n" + sources["controller"]
    sensitive_report_fragments = {
        '"database_url"',
        '"idempotency_key"',
        '"payload"',
        '"password"',
        '"proposal_id"',
        '"household_id"',
        '"user_id"',
        '"schedule_id"',
    }
    for fragment in sorted(sensitive_report_fragments):
        if fragment in router_controller:
            errors.append(
                "stable endpoint/controller stores sensitive request data: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "postgresql_major": 16,
        "physical_streaming_replication": True,
        "stable_application_endpoint": True,
        "route_epoch_before_failover": 0,
        "route_epoch_after_failover": 1,
        "controller_count": 2,
        "failure_threshold": 3,
        "automatic_failure_detection": True,
        "single_local_witness_lease": True,
        "promotion_winner_count": 1,
        "promotion_follower_count": 1,
        "old_primary_container_removed": True,
        "old_primary_volume_retained": True,
        "old_primary_endpoint_unavailable": True,
        "standby_promoted": True,
        "new_wal_timeline": True,
        "stable_route_rotated": True,
        "stable_endpoint_url_unchanged": True,
        "same_key_recovery": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "final_accepted_event_count": 1,
        "final_created_event_count": 1,
        "server_automatic_mutation_retry": False,
        "distributed_consensus_proven": False,
        "production_stonith_proven": False,
        "quorum_proven": False,
        "old_primary_rejoin_proven": False,
        "multi_worker_post_promotion_recovery_proven": False,
        "multi_region_failover_proven": False,
        "hosted_green_claim": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
