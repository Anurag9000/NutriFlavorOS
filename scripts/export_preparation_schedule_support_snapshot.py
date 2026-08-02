#!/usr/bin/env python3
"""Export one read-only, hash-addressed preparation support snapshot."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.api.database_error_handlers import classify_operational_error
from backend.database import SessionLocal
from backend.services.preparation_schedule_support_export_service import (
    export_preparation_schedule_support_snapshot,
)


def build_export_payload(
    db: Session,
    *,
    household_id: str,
    schedule_id: int,
) -> dict:
    export = export_preparation_schedule_support_snapshot(
        db,
        household_id=household_id,
        schedule_id=schedule_id,
    )
    return export.model_dump(mode="json")


def write_atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(
        f".{path.name}.tmp-{os.getpid()}"
    )
    try:
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export a read-only preparation schedule support snapshot. "
            "The command never performs lifecycle or task mutations."
        )
    )
    parser.add_argument("--household-id", required=True)
    parser.add_argument("--schedule-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.schedule_id < 1:
        _parser().error("--schedule-id must be at least 1")

    db = SessionLocal()
    try:
        payload = build_export_payload(
            db,
            household_id=args.household_id,
            schedule_id=args.schedule_id,
        )
        write_atomic_json(args.output, payload)
        summary = {
            "status": "exported",
            "output": str(args.output),
            "document_version": payload["document_version"],
            "household_id": payload["household_id"],
            "schedule_id": payload["schedule_id"],
            "evidence_hash": payload["evidence_hash"],
            "snapshot_read_only": payload["snapshot_read_only"],
            "mutation_performed": payload["mutation_performed"],
        }
        print(json.dumps(summary, sort_keys=True))
        return 0
    except HTTPException as exc:
        detail = exc.detail
        payload = {
            "status": "export_rejected",
            "http_status": exc.status_code,
            "detail": detail,
        }
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        return 2
    except OperationalError as exc:
        payload = {
            "status": "database_error",
            "detail": classify_operational_error(exc),
        }
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        return 3
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
