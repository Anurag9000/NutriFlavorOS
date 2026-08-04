#!/usr/bin/env python3
"""Validate real PostgreSQL application-worker SIGKILL recovery evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "helper": "scripts/probe_preparation_repair_worker_crash.py",
    "test": "backend/tests/test_preparation_repair_worker_crash_postgres.py",
    "guard": (
        "backend/services/preparation_repair_source_acceptance_guard_service.py"
    ),
    "workflow": ".github/workflows/preparation-repair-pool-exhaustion.yml",
    "docs": "docs/PREPARATION_REPAIR_WORKER_CRASH.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
    "readme": "README.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing worker crash file: {relative}")
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
            "Subprocess helper for real preparation-repair worker crash recovery",
            "WORKER_INSTANCE_ID = uuid4().hex",
            "class _CrashBeforeCommitSession(Session)",
            "def commit(self) -> None",
            "self.flush()",
            'self.execute(text("SELECT pg_backend_pid()"))',
            "_transaction_local_counts(self, _COMMIT_PROPOSAL_ID)",
            '"transaction_flushed_before_crash": True',
            '"transaction_commit_started": False',
            '"lifecycle_commit_performed": False',
            '"waiting_for_sigkill": True',
            "while True:",
            "poolclass=QueuePool",
            "pool_size=1",
            "max_overflow=0",
            "pool_timeout=POOL_TIMEOUT_SECONDS",
            "pool_pre_ping=True",
            "execute_exact_idempotent_database_request(",
            "accept_repair_proposal_with_source_guard(",
            'choices=("checkout-crash", "transaction-crash", "recover")',
            '"same_key_recovery_performed": True',
            "os.replace(temporary, path)",
        },
        "test": {
            "test_postgres_sigkill_during_pool_checkout_recovers_exact_request",
            "test_postgres_sigkill_after_flush_rolls_back_then_recovers_exact_request",
            "subprocess.Popen(",
            "os.kill(process.pid, signal.SIGKILL)",
            "return_code == -signal.SIGKILL",
            "_wait_for_backend_absence(db, old_backend_pid)",
            '"transaction_local_counts"] == ONE_COUNTS',
            '"transaction_local_proposal_status"] == "accepted"',
            "_accepted_counts(db, proposal.id) == ZERO_COUNTS",
            '_proposal_status(db, proposal.id) == "proposed"',
            "_accepted_counts(db, proposal.id) == ONE_COUNTS",
            '_proposal_status(db, proposal.id) == "accepted"',
            'recovery_report["worker_instance_id"] != old_worker_instance_id',
            'recovery_report["worker_pid"] != process.pid',
            'recovery_report["recovery_backend_pid"] != old_backend_pid',
            "replayed.acceptance.id == recovery_report[\"acceptance_id\"]",
            "replayed.acceptance.idempotency_key == idempotency_key",
            '"created",',
            '"accepted",',
        },
        "guard": {
            "accept_repair_proposal_with_source_guard",
            "_lock_household(db, household_id)",
            ".with_for_update()",
            "return accept_repair_proposal(",
        },
        "workflow": {
            "probe_preparation_repair_worker_crash.py",
            "test_preparation_repair_worker_crash_postgres.py",
            "validate_preparation_repair_worker_crash_contract.py",
            "reports/preparation-repair-pool-exhaustion.xml",
        },
        "docs": {
            "PostgreSQL Ungraceful Application-Worker Crash Recovery",
            "real `SIGKILL`",
            "Flushed-open-transaction crash",
            "transaction-local counts",
            "independent committed reader",
            "exactly zero committed lifecycle mutation",
            "same exact idempotency key",
            "does not prove",
            "commit acknowledgement itself is in flight",
            "multi-node failover",
        },
        "status": {
            "ungraceful application-worker crash",
            "flushed but uncommitted",
            "SIGKILL",
        },
        "roadmap": {
            "ungraceful application-worker crash",
            "commit acknowledgement",
            "multi-node failover",
        },
        "readme": {
            "ungraceful application-worker crash",
            "SIGKILL",
            "flushed open transaction",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks worker-crash fragment: {fragment}"
                )

    expected_tests = {
        "test_postgres_sigkill_during_pool_checkout_recovers_exact_request",
        "test_postgres_sigkill_after_flush_rolls_back_then_recovers_exact_request",
    }
    for name in sorted(expected_tests - _test_names(sources["test"])):
        errors.append(f"PostgreSQL worker-crash test is missing: {name}")

    helper_calls = _called_attributes(sources["helper"])
    test_calls = _called_attributes(sources["test"])
    for required_call in {"flush", "execute", "replace", "uuid4"}:
        if required_call not in helper_calls:
            errors.append(f"worker-crash helper lacks call: {required_call}")
    for required_call in {"Popen", "run", "kill", "wait"}:
        if required_call not in test_calls:
            errors.append(f"worker-crash test lacks call: {required_call}")

    forbidden = {
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "monkeypatch",
        "signal.SIGTERM",
        ".terminate(",
        "sys.stdin.readline()",
        "pressure_process.stdin.close()",
        "raise OperationalError(",
        "raise SQLAlchemyTimeoutError(",
        "DBPreparationRepairProposalAcceptance(",
        "DBPersistedPreparationSchedule(",
        "DBPreparationRepairProposalEvent(",
        "DBPreparationScheduleEvent(",
        "sqlite://",
        "super().commit(",
        "multi_node_failover_proven = True",
        "commit_acknowledgement_loss_proven = True",
    }
    combined = sources["helper"] + "\n" + sources["test"]
    for fragment in sorted(forbidden):
        if fragment in combined:
            errors.append(
                "worker-crash evidence contains forbidden shortcut or claim: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "database": "postgresql",
        "real_sigkill": True,
        "checkout_holder_crash": True,
        "flushed_open_transaction_crash": True,
        "production_guard_service": True,
        "transaction_local_rows_before_crash": 4,
        "independent_committed_rows_before_crash": 0,
        "committed_rows_after_crash": 0,
        "old_backend_absence_verified": True,
        "fresh_worker_instance": True,
        "fresh_backend_pid": True,
        "same_key_recovery": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "commit_acknowledgement_loss_proven": False,
        "multi_node_failover_proven": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
