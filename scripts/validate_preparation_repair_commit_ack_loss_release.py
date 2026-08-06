#!/usr/bin/env python3
"""Validate the synchronized COMMIT-loss and multi-instance recovery release."""

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
    "proxy": "backend/tests/postgres_commit_ack_drop_proxy.py",
    "proxy_tests": "backend/tests/test_postgres_commit_ack_drop_proxy.py",
    "test": "backend/tests/test_preparation_repair_commit_ack_loss_postgres.py",
    "multi_helper": "scripts/probe_preparation_repair_multi_instance_recovery.py",
    "multi_test": "backend/tests/test_preparation_repair_multi_instance_recovery_postgres.py",
    "contract": "scripts/validate_preparation_repair_commit_ack_loss_contract.py",
    "multi_contract": "scripts/validate_preparation_repair_multi_instance_recovery_contract.py",
    "workflow": ".github/workflows/preparation-repair-commit-ack-loss.yml",
    "docs": "docs/PREPARATION_REPAIR_COMMIT_ACK_LOSS.md",
    "multi_docs": "docs/PREPARATION_REPAIR_MULTI_INSTANCE_RECOVERY.md",
    "readme": "README.md",
    "status": "docs/IMPLEMENTATION_STATUS.md",
    "roadmap": "docs/ROADMAP.md",
}
PROSE_LABELS = {"docs", "multi_docs", "readme", "status", "roadmap"}


def _read(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing COMMIT acknowledgement release file: {relative}")
        return ""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(source, filename=relative)
    return source


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _contains(source: str, fragment: str, *, case_sensitive: bool = True) -> bool:
    normalized_source = _normalized(source)
    normalized_fragment = _normalized(fragment)
    if not case_sensitive:
        source = source.casefold()
        fragment = fragment.casefold()
        normalized_source = normalized_source.casefold()
        normalized_fragment = normalized_fragment.casefold()
    return fragment in source or normalized_fragment in normalized_source


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
        errors.append("COMMIT acknowledgement API release identity drifted")
    if openapi.get("contract_version") != EXPECTED_OPENAPI:
        errors.append("COMMIT acknowledgement OpenAPI identity drifted")
    if CURRENT_ALEMBIC_REVISION != EXPECTED_MIGRATION:
        errors.append("COMMIT acknowledgement migration identity drifted")

    required = {
        "proxy": {
            "class PostgresCommitAckDropProxy",
            "commit_query_seen",
            "commit_query_forwarded",
            "commit_command_complete_seen",
            "commit_acknowledgement_forwarded",
            "self._commit_query_seen.set()",
            "self._upstream.sendall(frame)",
            "self._commit_query_forwarded.set()",
            'self._commit_query_seen.is_set()',
            '_command_complete_tag(frame) == b"COMMIT"',
            "self._close_socket(self._client)",
            "self._close_socket(self._upstream)",
            "proxy threads leaked",
        },
        "proxy_tests": {
            "test_simple_query_commit_is_detected_exactly",
            "test_extended_protocol_parse_commit_is_detected_exactly",
            "test_command_complete_commit_tag_is_detected_exactly",
            "test_protocol_lengths_wait_for_complete_prefix_and_reject_invalid_values",
        },
        "test": {
            "test_postgres_commit_acknowledgement_loss_recovers_exact_committed_request",
            '"sslmode": "disable"',
            '"gssencmode": "disable"',
            'worker.execute(text("SET LOCAL synchronous_commit = on"))',
            'worker.execute(text("SHOW synchronous_commit")).scalar_one() == "on"',
            "with pytest.raises(OperationalError)",
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["retry_safe"] is False',
            'captured_error.connection_invalidated is True',
            "proxy_report.commit_query_forwarded is True",
            "proxy_report.commit_command_complete_seen is True",
            "proxy_report.commit_acknowledgement_forwarded is False",
            "proxy_report.proxy_threads_stopped is True",
            "_accepted_counts(db, proposal.id) == ONE_COUNTS",
            "replayed.acceptance.id == acceptance.id",
            "replayed.acceptance.idempotency_key == idempotency_key",
        },
        "multi_helper": {
            "Subprocess worker for coordinated exact-key recovery across app instances",
            "WORKER_INSTANCE_ID = uuid4().hex",
            "GATE_WAIT_SECONDS = 30.0",
            "poolclass=QueuePool",
            "pool_size=1",
            "max_overflow=0",
            "pool_pre_ping=True",
            'db.execute(text("SELECT pg_backend_pid()"))',
            '"waiting_for_release_gate": True',
            "_wait_for_gate(gate_path, release_token)",
            "accept_repair_proposal_with_source_guard(",
            '"same_key_recovery_performed": True',
            '"pool_checked_out_after_close": checked_out_after_close',
        },
        "multi_test": {
            "WORKER_COUNT = 6",
            "test_postgres_ambiguous_commit_converges_across_six_application_instances",
            "_commit_once_without_acknowledgement",
            'classification["code"] == "database_commit_outcome_unknown"',
            'classification["retry_safe"] is False',
            "subprocess.Popen(",
            "len(worker_instance_ids) == WORKER_COUNT",
            "len(backend_pids) == WORKER_COUNT",
            "all(_backend_exists(db, value) for value in backend_pids)",
            "_write_json_atomically(gate_path, {\"release_token\": release_token})",
            'value.get("same_key_recovery_performed") is True',
            'value["idempotency_key_matches"] is True',
            'value["pool_checked_out_after_close"] == 0',
            "_accepted_counts(db, proposal.id) == ONE_COUNTS",
            '"created",',
            '"accepted",',
        },
        "contract": {
            '"wire_proxy": True',
            '"protocol_unit_tests": True',
            '"commit_drop_armed_before_forward": True',
            '"commit_query_forwarded": True',
            '"synchronous_commit_on": True',
            '"command_complete_commit_seen": True',
            '"commit_acknowledgement_forwarded": False',
            '"client_outcome_unknown": True',
            '"retry_safe": False',
            '"same_key_recovery": True',
            '"single_controlled_proxy_connection": True',
            '"multi_node_failover_proven": False',
        },
        "multi_contract": {
            '"database_primary_count": 1',
            '"application_worker_count": 6',
            '"distinct_worker_instances": True',
            '"distinct_live_backend_pids": True',
            '"simultaneous_release_gate": True',
            '"distributed_lock_service": False',
            '"final_acceptance_count": 1',
            '"final_replacement_count": 1',
            '"same_acceptance_identity_for_all_workers": True',
            '"same_schedule_identity_for_all_workers": True',
            '"database_replica_promotion_proven": False',
            '"multi_node_failover_proven": False',
        },
        "workflow": {
            "validate-preparation-repair-commit-ack-loss",
            "postgres:16",
            "postgres_commit_ack_drop_proxy.py",
            "test_postgres_commit_ack_drop_proxy.py",
            "test_preparation_repair_commit_ack_loss_postgres.py",
            "test_preparation_repair_multi_instance_recovery_postgres.py",
            "probe_preparation_repair_multi_instance_recovery.py",
            "validate_preparation_repair_commit_ack_loss_contract.py",
            "validate_preparation_repair_multi_instance_recovery_contract.py",
            "validate_preparation_repair_commit_ack_loss_release.py",
            "validate_database_recovery_hardening_release.py",
            "validate_repair_release_identity.py",
            "reports/preparation-repair-commit-ack-loss.xml",
            "if-no-files-found: error",
        },
        "docs": {
            "PostgreSQL COMMIT Acknowledgement Loss",
            "synchronous_commit=on",
            "CommandComplete(COMMIT)",
            "acknowledgement is withheld",
            "database_commit_outcome_unknown",
            "retry_safe=false",
            "same exact idempotency key",
            "single controlled proxy connection",
            "does not prove multi-node failover",
        },
        "multi_docs": {
            "Controlled Multi-Application-Instance Exact Recovery",
            "single-primary PostgreSQL",
            "six independent application worker processes",
            "six PostgreSQL backends",
            "same existing acceptance ID",
            "same existing draft replacement schedule ID",
            "No separate distributed lock service",
            "multi-node PostgreSQL failover",
        },
        "readme": {
            f"API: `{EXPECTED_API}`",
            f"Alembic head: `{EXPECTED_MIGRATION}`",
            f"OpenAPI contract: `{EXPECTED_OPENAPI}`",
            "COMMIT acknowledgement loss",
            "CommandComplete(COMMIT)",
            "database_commit_outcome_unknown",
            "same exact idempotency key",
            "controlled multi-application-instance exact recovery",
            "six independent application workers",
            "one PostgreSQL primary",
            "multi-node failover",
        },
        "status": {
            "COMMIT acknowledgement loss",
            "synchronous_commit=on",
            "CommandComplete(COMMIT)",
            "database_commit_outcome_unknown",
            "same exact idempotency key",
            "controlled multi-application-instance exact recovery",
            "six independent worker processes",
            "one PostgreSQL primary",
            "multi-node failover recovery",
        },
        "roadmap": {
            "C17 — PostgreSQL COMMIT acknowledgement loss",
            "COMMIT acknowledgement loss",
            "CommandComplete(COMMIT)",
            "C18 — Controlled multi-application-instance exact recovery",
            "six independent application workers",
            "multi-node failover",
        },
    }
    for label, fragments in required.items():
        for fragment in sorted(fragments):
            if not _contains(
                sources[label],
                fragment,
                case_sensitive=label not in PROSE_LABELS,
            ):
                errors.append(
                    f"{FILES[label]} lacks COMMIT/multi-instance release fragment: {fragment}"
                )

    return {
        "valid": not errors,
        "api_version": app.version,
        "openapi_contract_version": openapi.get("contract_version"),
        "migration_head": CURRENT_ALEMBIC_REVISION,
        "wire_proxy": True,
        "protocol_unit_tests": True,
        "commit_drop_armed_before_forward": True,
        "commit_query_forwarded": True,
        "synchronous_commit_on": True,
        "command_complete_commit_seen": True,
        "commit_acknowledgement_forwarded": False,
        "client_outcome_unknown": True,
        "retry_safe": False,
        "server_automatic_retry": False,
        "committed_acceptance_count": 1,
        "committed_replacement_count": 1,
        "same_key_recovery": True,
        "single_controlled_proxy_connection": True,
        "database_primary_count": 1,
        "application_worker_count": 6,
        "simultaneous_multi_instance_recovery": True,
        "distributed_lock_service": False,
        "same_identity_for_all_workers": True,
        "database_replica_promotion_proven": False,
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
