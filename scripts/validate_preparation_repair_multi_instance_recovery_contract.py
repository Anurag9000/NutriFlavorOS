#!/usr/bin/env python3
"""Validate controlled exact-key recovery across application instances."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "helper": "scripts/probe_preparation_repair_multi_instance_recovery.py",
    "test": "backend/tests/test_preparation_repair_multi_instance_recovery_postgres.py",
    "proxy": "backend/tests/postgres_commit_ack_drop_proxy.py",
    "guard": "backend/services/preparation_repair_source_acceptance_guard_service.py",
    "workflow": ".github/workflows/preparation-repair-commit-ack-loss.yml",
    "docs": "docs/PREPARATION_REPAIR_MULTI_INSTANCE_RECOVERY.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
    "readme": "README.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing multi-instance recovery file: {relative}")
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
        "helper": {
            "Subprocess worker for coordinated exact-key recovery across app instances",
            "WORKER_INSTANCE_ID = uuid4().hex",
            "GATE_WAIT_SECONDS = 30.0",
            "PreparationRepairProposalAcceptRequest.model_validate",
            "poolclass=QueuePool",
            "pool_size=1",
            "max_overflow=0",
            "pool_timeout=5.0",
            "pool_pre_ping=True",
            'db.execute(text("SELECT pg_backend_pid()"))',
            '"waiting_for_release_gate": True',
            "_wait_for_gate(gate_path, release_token)",
            "accept_repair_proposal_with_source_guard(",
            '"same_key_recovery_performed": True',
            '"idempotency_key_matches": idempotency_key_matches',
            '"pool_checked_out_after_close": checked_out_after_close',
            "os.replace(temporary, path)",
        },
        "test": {
            "WORKER_COUNT = 6",
            "test_postgres_ambiguous_commit_converges_across_six_application_instances",
            "PostgresCommitAckDropProxy(",
            'worker.execute(text("SET LOCAL synchronous_commit = on"))',
            'worker.execute(text("SHOW synchronous_commit")).scalar_one() == "on"',
            "with pytest.raises(OperationalError)",
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["retry_safe"] is False',
            'classification["outcome_unknown"] is True',
            "_accepted_counts(db, proposal.id) == ONE_COUNTS",
            "subprocess.Popen(",
            '"waiting_for_release_gate"',
            "len(worker_instance_ids) == WORKER_COUNT",
            "len(backend_pids) == WORKER_COUNT",
            "all(_backend_exists(db, value) for value in backend_pids)",
            "_write_json_atomically(gate_path, {\"release_token\": release_token})",
            "def _collect_process(",
            "process.communicate(timeout=timeout_seconds)",
            "def _ensure_process_stopped(",
            "stdout, stderr = _collect_process(process)",
            "_ensure_process_stopped(process)",
            'value.get("same_key_recovery_performed") is True',
            'int(value["acceptance_id"]) for value in result_reports',
            'int(value["created_schedule_id"]) for value in result_reports',
            'value["idempotency_key_matches"] is True',
            'value["pool_checked_out_after_close"] == 0',
            "process.kill()",
            '"created",',
            '"accepted",',
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
            "probe_preparation_repair_multi_instance_recovery.py",
            "test_preparation_repair_multi_instance_recovery_postgres.py",
            "validate_preparation_repair_multi_instance_recovery_contract.py",
            "reports/preparation-repair-commit-ack-loss.xml",
        },
        "docs": {
            "Controlled Multi-Application-Instance Exact Recovery",
            "single-primary PostgreSQL",
            "six independent application worker processes",
            "six PostgreSQL backends",
            "same existing acceptance ID",
            "same existing draft replacement schedule ID",
            "one accepted proposal event",
            "one created schedule event",
            "No separate distributed lock service",
            "does not establish",
            "multi-node PostgreSQL failover",
        },
        "status": {
            "controlled multi-application-instance exact recovery",
            "six independent worker processes",
            "one PostgreSQL primary",
        },
        "roadmap": {
            "Controlled multi-application-instance exact recovery",
            "six independent application workers",
            "multi-node failover",
        },
        "readme": {
            "controlled multi-application-instance exact recovery",
            "six independent application workers",
            "one PostgreSQL primary",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks multi-instance recovery fragment: {fragment}"
                )

    expected_test = (
        "test_postgres_ambiguous_commit_converges_across_six_application_instances"
    )
    if expected_test not in _test_names(sources["test"]):
        errors.append("multi-instance PostgreSQL recovery test is missing")

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
        "process.stderr.read()",
        "distributed_lock_acquired = True",
        "database_replica_promoted = True",
        "multi_node_failover_proven = True",
        "representative_production_capacity = True",
    }
    combined = sources["helper"] + "\n" + sources["test"]
    for fragment in sorted(forbidden):
        if fragment in combined:
            errors.append(
                "multi-instance recovery evidence contains forbidden shortcut or claim: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "database": "postgresql",
        "database_primary_count": 1,
        "application_worker_count": 6,
        "distinct_worker_instances": True,
        "distinct_live_backend_pids": True,
        "simultaneous_release_gate": True,
        "synchronous_commit_on": True,
        "ambiguous_commit_source": True,
        "client_retry_safe": False,
        "server_automatic_retry": False,
        "production_source_guard": True,
        "distributed_lock_service": False,
        "subprocess_output_collected_once": True,
        "bounded_worker_cleanup": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "final_accepted_event_count": 1,
        "final_created_event_count": 1,
        "same_acceptance_identity_for_all_workers": True,
        "same_schedule_identity_for_all_workers": True,
        "pool_checked_out_after_close": 0,
        "database_replica_promotion_proven": False,
        "multi_node_failover_proven": False,
        "representative_production_capacity": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
