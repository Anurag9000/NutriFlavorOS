#!/usr/bin/env python3
"""Subprocess helper for controlled preparation-repair worker recycling.

This test helper receives committed proposal identities and an exact acceptance
payload through a temporary JSON file. It uses the production source-acceptance
guard and never fabricates lifecycle rows.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
)
from backend.exact_database_retry import (
    DatabaseRetryExhausted,
    ExactDatabaseRetryPolicy,
    execute_exact_idempotent_database_request,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)


POOL_TIMEOUT_SECONDS = 0.12


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("worker recycle configuration must be a JSON object")
    return value


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _engine(database_url: str):
    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=POOL_TIMEOUT_SECONDS,
        pool_pre_ping=True,
    )


def _validated_config(
    config: dict[str, Any],
) -> tuple[str, str, int, str, PreparationRepairProposalAcceptRequest]:
    database_url = str(config["database_url"])
    household_id = str(config["household_id"])
    proposal_id = int(config["proposal_id"])
    actor_user_id = str(config["actor_user_id"])
    payload = PreparationRepairProposalAcceptRequest.model_validate(
        config["payload"]
    )
    return database_url, household_id, proposal_id, actor_user_id, payload


def _pressure(config: dict[str, Any], report_path: Path) -> int:
    (
        database_url,
        household_id,
        proposal_id,
        actor_user_id,
        payload,
    ) = _validated_config(config)
    engine = _engine(database_url)
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    holder = engine.connect()
    holder_backend_pid = int(
        holder.execute(text("SELECT pg_backend_pid()" )).scalar_one()
    )

    def operation(exact_key: str, attempt: int):
        if exact_key != payload.idempotency_key or attempt != 1:
            raise AssertionError("pressure probe received a non-exact request")
        db = Session()
        try:
            return accept_repair_proposal_with_source_guard(
                db,
                household_id=household_id,
                proposal_id=proposal_id,
                actor_user_id=actor_user_id,
                payload=payload,
            )
        finally:
            db.close()

    try:
        execute_exact_idempotent_database_request(
            operation,
            idempotency_key=payload.idempotency_key,
            policy=ExactDatabaseRetryPolicy(
                max_attempts=1,
                base_delay_seconds=0,
                max_delay_seconds=0,
            ),
            sleep=lambda _: None,
        )
    except DatabaseRetryExhausted as exc:
        if len(exc.observations) != 1:
            raise AssertionError("pressure probe expected one failed checkout")
        observation = exc.observations[0]
    else:
        raise AssertionError("occupied worker pool unexpectedly accepted the proposal")

    report = {
        "mode": "pressure",
        "worker_pid": os.getpid(),
        "holder_backend_pid": holder_backend_pid,
        "pool_checked_out": engine.pool.checkedout(),
        "code": observation.code,
        "retry_safe": observation.retry_safe,
        "no_transaction_started": observation.no_transaction_started,
        "outcome_unknown": observation.outcome_unknown,
        "will_retry": observation.will_retry,
        "attempt": observation.attempt,
        "lifecycle_mutation_performed": False,
        "waiting_for_orderly_recycle": True,
        "recycle_completed": False,
    }
    _write_json_atomically(report_path, report)

    # The parent closes stdin to request an orderly application-worker recycle.
    # The checked-out connection remains live until that explicit recycle point.
    sys.stdin.readline()
    holder.close()
    checked_out_after_close = engine.pool.checkedout()
    engine.dispose()
    report.update(
        {
            "waiting_for_orderly_recycle": False,
            "recycle_completed": True,
            "pool_checked_out_after_close": checked_out_after_close,
        }
    )
    _write_json_atomically(report_path, report)
    return 0


def _recover(config: dict[str, Any], report_path: Path) -> int:
    (
        database_url,
        household_id,
        proposal_id,
        actor_user_id,
        payload,
    ) = _validated_config(config)
    engine = _engine(database_url)
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    db = Session()
    try:
        recovery_backend_pid = int(
            db.execute(text("SELECT pg_backend_pid()" )).scalar_one()
        )
        accepted = accept_repair_proposal_with_source_guard(
            db,
            household_id=household_id,
            proposal_id=proposal_id,
            actor_user_id=actor_user_id,
            payload=payload,
        )
        acceptance_id = int(accepted.acceptance.id)
        schedule_id = int(accepted.acceptance.created_schedule_id)
        schedule_version = int(accepted.acceptance.created_schedule_version)
        schedule_status = str(accepted.acceptance.created_schedule_status)
    finally:
        db.close()
    checked_out_after_close = engine.pool.checkedout()
    engine.dispose()

    _write_json_atomically(
        report_path,
        {
            "mode": "recovery",
            "worker_pid": os.getpid(),
            "recovery_backend_pid": recovery_backend_pid,
            "acceptance_id": acceptance_id,
            "created_schedule_id": schedule_id,
            "created_schedule_version": schedule_version,
            "created_schedule_status": schedule_status,
            "pool_checked_out_after_close": checked_out_after_close,
            "same_key_recovery_performed": True,
        },
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("pressure", "recover"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    try:
        config = _read_json(args.config)
        if args.mode == "pressure":
            return _pressure(config, args.report)
        return _recover(config, args.report)
    except Exception as exc:  # pragma: no cover - diagnostic subprocess boundary
        _write_json_atomically(
            args.report,
            {
                "mode": args.mode,
                "worker_pid": os.getpid(),
                "error_type": type(exc).__name__,
                "success": False,
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
