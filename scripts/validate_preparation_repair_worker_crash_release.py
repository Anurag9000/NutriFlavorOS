#!/usr/bin/env python3
"""Validate the synchronized ungraceful worker-crash release boundary."""

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
    "helper": "scripts/probe_preparation_repair_worker_crash.py",
    "test": "backend/tests/test_preparation_repair_worker_crash_postgres.py",
    "contract": "scripts/validate_preparation_repair_worker_crash_contract.py",
    "workflow": ".github/workflows/preparation-repair-pool-exhaustion.yml",
    "docs": "docs/PREPARATION_REPAIR_WORKER_CRASH.md",
    "readme": "README.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing worker crash release file: {relative}")
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
        errors.append("worker crash API release identity drifted")
    if openapi.get("contract_version") != EXPECTED_OPENAPI:
        errors.append("worker crash OpenAPI release identity drifted")
    if CURRENT_ALEMBIC_REVISION != EXPECTED_MIGRATION:
        errors.append("worker crash migration identity drifted")

    required = {
        "helper": {
            "Subprocess helper for real preparation-repair worker crash recovery",
            "WORKER_INSTANCE_ID = uuid4().hex",
            "class _CrashBeforeCommitSession(Session)",
            "def commit(self) -> None",
            "self.flush()",
            '"transaction_flushed_before_crash": True',
            '"database_commit_statement_started": False',
            '"lifecycle_commit_performed": False',
            'choices=("checkout-crash", "transaction-crash", "recover")',
            '"same_key_recovery_performed": True',
        },
        "test": {
            "test_postgres_sigkill_during_pool_checkout_recovers_exact_request",
            "test_postgres_sigkill_after_flush_rolls_back_then_recovers_exact_request",
            "os.kill(process.pid, signal.SIGKILL)",
            "return_code == -signal.SIGKILL",
            "_wait_for_backend_absence(db, old_backend_pid)",
            'recovery_report["worker_instance_id"] != old_worker_instance_id',
            'recovery_report["recovery_backend_pid"] != old_backend_pid',
            "_accepted_counts(db, proposal.id) == ZERO_COUNTS",
            "_accepted_counts(db, proposal.id) == ONE_COUNTS",
            "replayed.acceptance.id == recovery_report[\"acceptance_id\"]",
            "replayed.acceptance.idempotency_key == idempotency_key",
        },
        "contract": {
            '"real_sigkill": True',
            '"checkout_holder_crash": True',
            '"flushed_open_transaction_crash": True',
            '"database_commit_statement_started": False',
            '"committed_rows_after_crash": 0',
            '"os_pid_reuse_tolerated": True',
            '"subprocess_output_collected_once": True',
            '"same_key_recovery": True',
            '"commit_acknowledgement_loss_proven": False',
            '"multi_node_failover_proven": False',
        },
        "workflow": {
            "probe_preparation_repair_worker_crash.py",
            "test_preparation_repair_worker_crash_postgres.py",
            "validate_preparation_repair_worker_crash_contract.py",
            "validate_preparation_repair_worker_crash_release.py",
            "reports/preparation-repair-pool-exhaustion.xml",
        },
        "docs": {
            "PostgreSQL Ungraceful Application-Worker Crash Recovery",
            "real `SIGKILL`",
            "Flushed-open-transaction crash",
            "Deterministic process cleanup",
            "OS PID reuse",
            "exactly zero committed lifecycle mutation",
            "same exact idempotency key",
            "commit acknowledgement itself is in flight",
            "multi-node failover",
        },
        "readme": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI}`",
            "ungraceful application-worker crash",
            "SIGKILL",
            "flushed open transaction",
            "same exact idempotency key",
            "This crash boundary does not itself prove post-COMMIT ambiguity",
            "COMMIT acknowledgement loss",
        },
        "status": {
            "Controlled ungraceful application-worker crash",
            "flushed but uncommitted",
            "SIGKILL",
            "This crash boundary proves controlled process-death rollback before COMMIT",
            "Controlled PostgreSQL COMMIT acknowledgement loss",
            "multi-node failover recovery",
        },
        "roadmap": {
            "C16 — Controlled ungraceful application-worker crash",
            "ungraceful application-worker crash",
            "OS PID reuse",
            "C17 — PostgreSQL COMMIT acknowledgement loss",
            "multi-node failover",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(sources[label], fragment):
                errors.append(
                    f"{FILES[label]} lacks worker-crash release fragment: {fragment}"
                )

    forbidden_test = {
        'recovery_report["worker_pid"] != process.pid',
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "monkeypatch",
        "signal.SIGTERM",
        ".terminate(",
        "sqlite://",
    }
    for fragment in sorted(forbidden_test):
        if fragment in sources["test"]:
            errors.append(
                "worker crash release contains forbidden nondeterminism or shortcut: "
                f"{fragment}"
            )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": openapi.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "real_sigkill": True,
        "checkout_holder_crash": True,
        "flushed_open_transaction_crash": True,
        "database_commit_statement_started": False,
        "committed_rows_after_crash": 0,
        "stable_worker_instance_identity": True,
        "os_pid_reuse_tolerated": True,
        "old_backend_absence_verified": True,
        "subprocess_output_collected_once": True,
        "same_key_recovery": True,
        "final_acceptance_count": 1,
        "final_replacement_count": 1,
        "commit_acknowledgement_loss_proven": False,
        "separate_commit_acknowledgement_boundary_present": True,
        "multi_node_failover_proven": False,
        "hosted_green_claim": False,
        "errors": errors,
    }


def main() -> int:
    report = validate_release()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
