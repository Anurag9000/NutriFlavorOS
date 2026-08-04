#!/usr/bin/env python3
"""Subprocess helper for real preparation-repair worker crash recovery.

The helper uses committed proposal inputs and the production source-acceptance
guard. Crash modes intentionally keep a live PostgreSQL connection or a flushed
open transaction until the parent sends SIGKILL. No lifecycle row is fabricated.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
)
from backend.exact_database_retry import (
    DatabaseRetryExhausted,
    ExactDatabaseRetryPolicy,
    execute_exact_idempotent_database_request,
)
from backend.preparation_operations_models import (
    DBPersistedPreparationSchedule,
    DBPreparationScheduleEvent,
)
from backend.preparation_repair_proposal_models import (
    DBPreparationRepairProposal,
    DBPreparationRepairProposalAcceptance,
    DBPreparationRepairProposalEvent,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)


POOL_TIMEOUT_SECONDS = 0.12
WORKER_INSTANCE_ID = uuid4().hex
_COMMIT_REPORT_PATH: Path | None = None
_COMMIT_ENGINE: Engine | None = None
_COMMIT_PROPOSAL_ID: int | None = None


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("worker crash configuration must be a JSON object")
    return value


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _engine(database_url: str) -> Engine:
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


def _enum_or_string(value: object) -> str:
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def _transaction_local_counts(db: Session, proposal_id: int) -> dict[str, int]:
    return {
        "acceptances": (
            db.query(DBPreparationRepairProposalAcceptance)
            .filter(DBPreparationRepairProposalAcceptance.proposal_id == proposal_id)
            .count()
        ),
        "replacement_schedules": (
            db.query(DBPersistedPreparationSchedule)
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == proposal_id
            )
            .count()
        ),
        "proposal_accepted_events": (
            db.query(DBPreparationRepairProposalEvent)
            .filter(
                DBPreparationRepairProposalEvent.proposal_id == proposal_id,
                DBPreparationRepairProposalEvent.event_type == "accepted",
            )
            .count()
        ),
        "replacement_created_events": (
            db.query(DBPreparationScheduleEvent)
            .join(
                DBPersistedPreparationSchedule,
                DBPersistedPreparationSchedule.id
                == DBPreparationScheduleEvent.schedule_id,
            )
            .filter(
                DBPersistedPreparationSchedule.source_repair_proposal_id
                == proposal_id,
                DBPreparationScheduleEvent.event_type == "created",
            )
            .count()
        ),
    }


class _CrashBeforeCommitSession(Session):
    """Flush production mutations, publish proof, and wait for real SIGKILL."""

    def commit(self) -> None:
        if (
            _COMMIT_REPORT_PATH is None
            or _COMMIT_ENGINE is None
            or _COMMIT_PROPOSAL_ID is None
        ):
            raise AssertionError("crash-before-commit session was not configured")

        self.flush()
        backend_pid = int(
            self.execute(text("SELECT pg_backend_pid()")).scalar_one()
        )
        proposal = self.get(DBPreparationRepairProposal, _COMMIT_PROPOSAL_ID)
        if proposal is None:
            raise AssertionError("flushed crash transaction lost its proposal")
        local_counts = _transaction_local_counts(self, _COMMIT_PROPOSAL_ID)
        if local_counts != {
            "acceptances": 1,
            "replacement_schedules": 1,
            "proposal_accepted_events": 1,
            "replacement_created_events": 1,
        }:
            raise AssertionError(
                f"unexpected transaction-local lifecycle counts: {local_counts}"
            )

        _write_json_atomically(
            _COMMIT_REPORT_PATH,
            {
                "mode": "transaction-crash",
                "worker_instance_id": WORKER_INSTANCE_ID,
                "worker_pid": os.getpid(),
                "backend_pid": backend_pid,
                "pool_checked_out": _COMMIT_ENGINE.pool.checkedout(),
                "transaction_flushed_before_crash": True,
                "commit_method_intercepted": True,
                "database_commit_statement_started": False,
                "transaction_local_counts": local_counts,
                "transaction_local_proposal_status": proposal.status,
                "waiting_for_sigkill": True,
                "lifecycle_commit_performed": False,
            },
        )
        while True:
            time.sleep(3600)


def _checkout_crash(config: dict[str, Any], report_path: Path) -> int:
    (
        database_url,
        household_id,
        proposal_id,
        actor_user_id,
        payload,
    ) = _validated_config(config)
    engine = _engine(database_url)
    SessionFactory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    holder = engine.connect()
    holder_backend_pid = int(
        holder.execute(text("SELECT pg_backend_pid()")).scalar_one()
    )

    def operation(exact_key: str, attempt: int):
        if exact_key != payload.idempotency_key or attempt != 1:
            raise AssertionError("checkout crash probe received a non-exact request")
        db = SessionFactory()
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
            raise AssertionError("checkout crash expected one failed checkout")
        observation = exc.observations[0]
    else:
        raise AssertionError("occupied crash-worker pool accepted the proposal")

    _write_json_atomically(
        report_path,
        {
            "mode": "checkout-crash",
            "worker_instance_id": WORKER_INSTANCE_ID,
            "worker_pid": os.getpid(),
            "holder_backend_pid": holder_backend_pid,
            "pool_checked_out": engine.pool.checkedout(),
            "code": observation.code,
            "retry_safe": observation.retry_safe,
            "no_transaction_started": observation.no_transaction_started,
            "outcome_unknown": observation.outcome_unknown,
            "will_retry": observation.will_retry,
            "lifecycle_mutation_performed": False,
            "waiting_for_sigkill": True,
        },
    )
    while True:
        time.sleep(3600)


def _transaction_crash(config: dict[str, Any], report_path: Path) -> int:
    global _COMMIT_ENGINE, _COMMIT_PROPOSAL_ID, _COMMIT_REPORT_PATH

    (
        database_url,
        household_id,
        proposal_id,
        actor_user_id,
        payload,
    ) = _validated_config(config)
    engine = _engine(database_url)
    _COMMIT_ENGINE = engine
    _COMMIT_PROPOSAL_ID = proposal_id
    _COMMIT_REPORT_PATH = report_path
    SessionFactory = sessionmaker(
        bind=engine,
        class_=_CrashBeforeCommitSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    db = SessionFactory()
    accept_repair_proposal_with_source_guard(
        db,
        household_id=household_id,
        proposal_id=proposal_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )
    raise AssertionError("transaction crash probe returned past intercepted commit")


def _recover(config: dict[str, Any], report_path: Path) -> int:
    (
        database_url,
        household_id,
        proposal_id,
        actor_user_id,
        payload,
    ) = _validated_config(config)
    engine = _engine(database_url)
    SessionFactory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    db = SessionFactory()
    try:
        recovery_backend_pid = int(
            db.execute(text("SELECT pg_backend_pid()")).scalar_one()
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
        schedule_status = _enum_or_string(
            accepted.acceptance.created_schedule_status
        )
    finally:
        db.close()
    checked_out_after_close = engine.pool.checkedout()
    engine.dispose()

    _write_json_atomically(
        report_path,
        {
            "mode": "recovery",
            "worker_instance_id": WORKER_INSTANCE_ID,
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
    parser.add_argument(
        "mode",
        choices=("checkout-crash", "transaction-crash", "recover"),
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    try:
        config = _read_json(args.config)
        if args.mode == "checkout-crash":
            return _checkout_crash(config, args.report)
        if args.mode == "transaction-crash":
            return _transaction_crash(config, args.report)
        return _recover(config, args.report)
    except Exception as exc:  # pragma: no cover - subprocess diagnostics
        _write_json_atomically(
            args.report,
            {
                "mode": args.mode,
                "worker_instance_id": WORKER_INSTANCE_ID,
                "worker_pid": os.getpid(),
                "error_type": type(exc).__name__,
                "success": False,
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
