#!/usr/bin/env python3
"""Subprocess worker for coordinated exact-key recovery across app instances.

Each process opens its own PostgreSQL connection, publishes a stable worker
identity and backend PID, waits for the parent release gate, and invokes the
production source-acceptance guard with the exact committed request. The helper
never constructs lifecycle rows directly and never retries an ambiguous request
without the explicit parent-controlled recovery phase.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from backend.domain.preparation_repair_proposals import (
    PreparationRepairProposalAcceptRequest,
)
from backend.services.preparation_repair_source_acceptance_guard_service import (
    accept_repair_proposal_with_source_guard,
)


WORKER_INSTANCE_ID = uuid4().hex
GATE_WAIT_SECONDS = 30.0


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("multi-instance recovery config must be a JSON object")
    return value


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _enum_or_string(value: object) -> str:
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def _safe_error(exc: Exception) -> dict[str, Any]:
    """Return bounded, credential-free subprocess diagnostics."""

    detail: object = None
    if isinstance(exc, HTTPException):
        detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code")
        message = detail.get("message")
    else:
        code = None
        message = detail if isinstance(detail, str) else str(exc)
    return {
        "error_type": type(exc).__name__,
        "error_code": str(code)[:160] if code is not None else None,
        "error_message": str(message)[:500] if message else None,
    }


def _wait_for_gate(path: Path, token: str) -> None:
    deadline = time.monotonic() + GATE_WAIT_SECONDS
    while time.monotonic() < deadline:
        if path.is_file():
            payload = _read_json(path)
            if payload.get("release_token") == token:
                return
        time.sleep(0.02)
    raise TimeoutError("multi-instance recovery release gate was not opened")


def run_worker(
    *,
    config_path: Path,
    ready_path: Path,
    gate_path: Path,
    result_path: Path,
) -> int:
    config = _read_json(config_path)
    database_url = str(config["database_url"])
    household_id = str(config["household_id"])
    proposal_id = int(config["proposal_id"])
    actor_user_id = str(config["actor_user_id"])
    release_token = str(config["release_token"])
    payload = PreparationRepairProposalAcceptRequest.model_validate(config["payload"])

    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=5.0,
        pool_pre_ping=True,
    )
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    db = Session()
    try:
        backend_pid = int(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
        _write_json_atomically(
            ready_path,
            {
                "worker_instance_id": WORKER_INSTANCE_ID,
                "worker_pid": os.getpid(),
                "backend_pid": backend_pid,
                "proposal_id": proposal_id,
                "waiting_for_release_gate": True,
            },
        )
        _wait_for_gate(gate_path, release_token)
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
        idempotency_key_matches = (
            accepted.acceptance.idempotency_key == payload.idempotency_key
        )
    finally:
        db.close()
    checked_out_after_close = engine.pool.checkedout()
    engine.dispose()

    _write_json_atomically(
        result_path,
        {
            "worker_instance_id": WORKER_INSTANCE_ID,
            "worker_pid": os.getpid(),
            "backend_pid": backend_pid,
            "proposal_id": proposal_id,
            "acceptance_id": acceptance_id,
            "created_schedule_id": schedule_id,
            "created_schedule_version": schedule_version,
            "created_schedule_status": schedule_status,
            "idempotency_key_matches": idempotency_key_matches,
            "pool_checked_out_after_close": checked_out_after_close,
            "same_key_recovery_performed": True,
        },
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()

    try:
        return run_worker(
            config_path=args.config,
            ready_path=args.ready,
            gate_path=args.gate,
            result_path=args.result,
        )
    except Exception as exc:  # pragma: no cover - subprocess diagnostic boundary
        _write_json_atomically(
            args.result,
            {
                "worker_instance_id": WORKER_INSTANCE_ID,
                "worker_pid": os.getpid(),
                "success": False,
                **_safe_error(exc),
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
