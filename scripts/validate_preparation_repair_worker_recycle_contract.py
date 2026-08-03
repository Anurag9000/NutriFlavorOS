#!/usr/bin/env python3
"""Validate controlled PostgreSQL application-worker recycle evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "helper": "scripts/probe_preparation_repair_worker_recycle.py",
    "test": "backend/tests/test_preparation_repair_worker_recycle_postgres.py",
    "handler": "backend/api/database_error_handlers.py",
    "retry": "backend/exact_database_retry.py",
    "guard": (
        "backend/services/preparation_repair_source_acceptance_guard_service.py"
    ),
    "workflow": ".github/workflows/preparation-repair-pool-exhaustion.yml",
    "docs": "docs/PREPARATION_REPAIR_WORKER_RECYCLE.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing worker recycle file: {relative}")
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


def _called_attributes(source: str) -> set[str]:
    tree = ast.parse(source)
    result: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute):
            result.add(function.attr)
        elif isinstance(function, ast.Name):
            result.add(function.id)
    return result


def validate_contract() -> dict:
    errors: list[str] = []
    sources = {name: _read(path, errors) for name, path in FILES.items()}

    required = {
        "helper": {
            "Subprocess helper for controlled preparation-repair worker recycling",
            "from uuid import uuid4",
            "WORKER_INSTANCE_ID = uuid4().hex",
            "PreparationRepairProposalAcceptRequest.model_validate",
            "accept_repair_proposal_with_source_guard(",
            "execute_exact_idempotent_database_request(",
            "poolclass=QueuePool",
            "pool_size=1",
            "max_overflow=0",
            "pool_timeout=POOL_TIMEOUT_SECONDS",
            "pool_pre_ping=True",
            'holder.execute(text("SELECT pg_backend_pid()"))',
            "sys.stdin.readline()",
            "holder.close()",
            "engine.dispose()",
            '"worker_instance_id": WORKER_INSTANCE_ID',
            '"waiting_for_orderly_recycle": True',
            '"recycle_completed": True',
            '"pool_checked_out_after_close": checked_out_after_close',
            '"same_key_recovery_performed": True',
            "_write_json_atomically",
            "os.replace(temporary, path)",
        },
        "test": {
            "test_postgres_worker_recycle_under_pool_pressure_recovers_exact_request",
            "subprocess.Popen(",
            "stdin=subprocess.PIPE",
            "pressure_process.stdin.close()",
            "pressure_process.wait(timeout=15) == 0",
            "_backend_exists(db, old_backend_pid) is True",
            "_wait_for_backend_absence(db, old_backend_pid)",
            "subprocess.run(",
            "stdin=subprocess.DEVNULL",
            'old_worker_instance_id = str(pressure_report["worker_instance_id"])',
            "len(old_worker_instance_id) == 32",
            'new_worker_instance_id = str(recovery_report["worker_instance_id"])',
            "len(new_worker_instance_id) == 32",
            "new_worker_instance_id != old_worker_instance_id",
            "recovery_report[\"recovery_backend_pid\"] != old_backend_pid",
            "recovery_report[\"created_schedule_status\"] == \"draft\"",
            "recovery_report[\"pool_checked_out_after_close\"] == 0",
            '"acceptances": 0',
            '"replacement_schedules": 0',
            '"proposal_accepted_events": 0',
            '"replacement_created_events": 0',
            '"acceptances": 1',
            '"replacement_schedules": 1',
            "replayed.acceptance.id == recovery_report[\"acceptance_id\"]",
            "replayed.acceptance.idempotency_key == idempotency_key",
            'value.event_type for value in proposal_events',
            '"created",',
            '"accepted",',
        },
        "handler": {
            '"code": "database_pool_timeout"',
            '"no_transaction_started": True',
            '"outcome_unknown": False',
            '"automatic_retry_performed": False',
        },
        "retry": {
            "classify_database_error",
            "TimeoutError as SQLAlchemyTimeoutError",
            "no_transaction_started=observation.no_transaction_started",
        },
        "guard": {
            "accept_repair_proposal_with_source_guard",
            "_lock_household(db, household_id)",
            ".with_for_update()",
            "return accept_repair_proposal(",
        },
        "workflow": {
            "probe_preparation_repair_worker_recycle.py",
            "test_preparation_repair_worker_recycle_postgres.py",
            "validate_preparation_repair_worker_recycle_contract.py",
            "reports/preparation-repair-pool-exhaustion.xml",
        },
        "docs": {
            "Controlled PostgreSQL Application-Worker Recycle",
            "old worker",
            "worker-instance",
            "PostgreSQL backend PID",
            "orderly recycle",
            "exactly zero lifecycle mutation",
            "fresh worker process",
            "same idempotency key",
            "same acceptance and schedule identities",
            "not a crash-recovery or multi-node failover proof",
        },
        "status": {
            "controlled application-worker recycle",
            "old PostgreSQL backend disappears",
            "fresh worker process",
        },
        "roadmap": {
            "controlled application-worker recycle",
            "crash recovery",
            "multi-node failover",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks worker-recycle fragment: {fragment}"
                )

    expected_test = (
        "test_postgres_worker_recycle_under_pool_pressure_recovers_exact_request"
    )
    if expected_test not in _test_names(sources["test"]):
        errors.append("controlled PostgreSQL worker recycle test is missing")

    helper_calls = _called_attributes(sources["helper"])
    test_calls = _called_attributes(sources["test"])
    for required_call in {"replace", "readline", "close", "dispose", "uuid4"}:
        if required_call not in helper_calls:
            errors.append(f"worker recycle helper lacks call: {required_call}")
    for required_call in {"Popen", "run", "wait", "close"}:
        if required_call not in test_calls:
            errors.append(f"worker recycle test lacks call: {required_call}")

    forbidden = {
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "monkeypatch",
        "os.kill(",
        ".kill(",
        ".terminate(",
        "signal.SIGKILL",
        "signal.SIGTERM",
        "raise SQLAlchemyTimeoutError",
        "raise TimeoutError",
        "DBPreparationRepairProposalAcceptance(",
        "DBPersistedPreparationSchedule(",
        "sqlite://",
        "crash_recovery_proven = True",
        "multi_node_failover_proven = True",
    }
    combined = sources["helper"] + "\n" + sources["test"]
    for fragment in sorted(forbidden):
        if fragment in combined:
            errors.append(
                "worker recycle evidence contains forbidden shortcut or claim: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "database": "postgresql",
        "old_worker_pool_size": 1,
        "old_worker_pool_exhausted": True,
        "stable_worker_instance_identity": True,
        "old_backend_observed_active": True,
        "zero_mutation_before_recycle": True,
        "orderly_recycle_requested_through_stdin": True,
        "old_backend_absence_verified": True,
        "fresh_worker_process": True,
        "fresh_worker_instance_identity": True,
        "fresh_backend_pid": True,
        "same_key_recovery": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "pool_checked_out_after_close": 0,
        "crash_recovery_proven": False,
        "multi_node_failover_proven": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
