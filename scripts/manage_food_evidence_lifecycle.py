#!/usr/bin/env python3
"""Dry-run or atomically apply immutable evidence lifecycle actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.database import SessionLocal
from backend.domain.evidence_lifecycle import EvidenceLifecycleBatchDocument
from backend.services.evidence_lifecycle_preflight import (
    preflight_evidence_lifecycle_batch,
)
from backend.services.evidence_lifecycle_service import (
    apply_evidence_lifecycle_batch,
)


TOOL_VERSION = "immutable-evidence-lifecycle-v1"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> EvidenceLifecycleBatchDocument:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    return EvidenceLifecycleBatchDocument.model_validate(raw)


def _manifest_hash(value: dict) -> str:
    payload = dict(value)
    payload.pop("manifest_sha256", None)
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _finalize(value: dict) -> dict:
    result = dict(value)
    result["completed_at"] = utcnow().isoformat()
    result["manifest_sha256"] = _manifest_hash(result)
    return result


def _write_manifest(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def default_manifest_path(input_path: Path) -> Path:
    return input_path.with_suffix(input_path.suffix + ".lifecycle-manifest.json")


def _base_manifest(
    *,
    input_path: Path,
    input_hash: str | None,
    operator: str | None,
    apply: bool,
) -> dict:
    return {
        "protocol_version": "immutable_evidence_lifecycle_manifest_v1",
        "tool_version": TOOL_VERSION,
        "repository_commit": (
            os.getenv("NUTRIFLAVOR_COMMIT_SHA")
            or os.getenv("GITHUB_SHA")
            or "unknown"
        ),
        "mode": "apply" if apply else "dry_run",
        "operator": operator or "unspecified",
        "input_path": str(input_path),
        "input_sha256": input_hash,
        "started_at": utcnow().isoformat(),
        "completed_at": None,
        "database_dialect": None,
        "document_version": None,
        "action_count": 0,
        "rows": [],
        "status": "started",
        "atomic": True,
        "database_committed": False,
        "changed_target_count": 0,
        "already_inactive_count": 0,
        "idempotent_count": 0,
        "error": None,
        "limitations": [
            "A lifecycle event never rewrites immutable evidence content.",
            "Reactivation is intentionally unsupported; corrected active evidence requires a new version.",
            "Manifest hashing detects modification but does not authenticate the source operator.",
            "A dry run does not reserve targets or idempotency keys against future concurrent actions."
        ]
    }


def _write_or_fail(
    *,
    path: Path,
    manifest: dict,
    database_committed: bool,
) -> tuple[int, dict] | None:
    try:
        _write_manifest(path, manifest)
        return None
    except OSError as exc:
        failed = dict(manifest)
        failed.pop("manifest_sha256", None)
        failed.update(
            {
                "status": (
                    "applied_manifest_write_failed"
                    if database_committed
                    else "manifest_write_failed"
                ),
                "database_committed": database_committed,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "stage": "write_manifest",
                    "database_already_committed": database_committed,
                },
            }
        )
        return (4 if database_committed else 2), _finalize(failed)


def run_lifecycle(
    *,
    input_path: Path,
    manifest_path: Path,
    apply: bool,
    operator: str | None,
) -> tuple[int, dict]:
    database_committed = False
    try:
        input_hash = file_sha256(input_path)
    except OSError as exc:
        manifest = _base_manifest(
            input_path=input_path,
            input_hash=None,
            operator=operator,
            apply=apply,
        )
        manifest.update(
            {
                "status": "failed",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "stage": "read_input",
                },
            }
        )
        finalized = _finalize(manifest)
        failure = _write_or_fail(
            path=manifest_path,
            manifest=finalized,
            database_committed=False,
        )
        return failure or (2, finalized)

    manifest = _base_manifest(
        input_path=input_path,
        input_hash=input_hash,
        operator=operator,
        apply=apply,
    )
    if apply and (not operator or not operator.strip()):
        manifest.update(
            {
                "status": "failed",
                "error": {
                    "type": "ValueError",
                    "message": "--operator is required for --apply",
                    "stage": "operator_validation",
                },
            }
        )
        finalized = _finalize(manifest)
        failure = _write_or_fail(
            path=manifest_path,
            manifest=finalized,
            database_committed=False,
        )
        return failure or (2, finalized)

    try:
        document = _load(input_path)
    except (OSError, json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        manifest.update(
            {
                "status": "failed",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "stage": "schema_validation",
                },
            }
        )
        finalized = _finalize(manifest)
        failure = _write_or_fail(
            path=manifest_path,
            manifest=finalized,
            database_committed=False,
        )
        return failure or (2, finalized)

    actors = sorted({value.actor for value in document.actions})
    if apply and any(value != operator.strip() for value in actors):
        manifest.update(
            {
                "document_version": document.document_version,
                "action_count": len(document.actions),
                "status": "failed",
                "error": {
                    "type": "ValueError",
                    "message": "Every action actor must exactly match --operator",
                    "stage": "actor_validation",
                    "document_actors": actors,
                },
            }
        )
        finalized = _finalize(manifest)
        failure = _write_or_fail(
            path=manifest_path,
            manifest=finalized,
            database_committed=False,
        )
        return failure or (2, finalized)

    manifest.update(
        {
            "document_version": document.document_version,
            "action_count": len(document.actions),
            "document_actors": actors,
        }
    )
    db = SessionLocal()
    try:
        manifest["database_dialect"] = db.get_bind().dialect.name
        previews = preflight_evidence_lifecycle_batch(db, document)
        manifest["rows"] = [value.to_dict() for value in previews]
        if not apply:
            manifest["status"] = "validated_dry_run"
            finalized = _finalize(manifest)
            failure = _write_or_fail(
                path=manifest_path,
                manifest=finalized,
                database_committed=False,
            )
            return failure or (0, finalized)

        manifest["status"] = "validated_pending_apply"
        pending = _finalize(manifest)
        failure = _write_or_fail(
            path=manifest_path,
            manifest=pending,
            database_committed=False,
        )
        if failure:
            return failure

        result = apply_evidence_lifecycle_batch(db, document)
        database_committed = True
        event_by_key = {value.idempotency_key: value for value in result.events}
        final_rows = []
        for preview in previews:
            event = event_by_key[preview.idempotency_key]
            row = preview.to_dict()
            row.update(
                {
                    "event_id": event.id,
                    "outcome": (
                        "idempotent_existing"
                        if preview.planned_action == "idempotent_existing"
                        else "recorded"
                    ),
                    "target_was_active": event.target_was_active,
                    "event_created_at": event.created_at,
                }
            )
            final_rows.append(row)
        manifest.update(
            {
                "rows": final_rows,
                "status": "applied",
                "database_committed": True,
                "changed_target_count": result.changed_target_count,
                "already_inactive_count": result.already_inactive_count,
                "idempotent_count": result.idempotent_count,
            }
        )
        finalized = _finalize(manifest)
        failure = _write_or_fail(
            path=manifest_path,
            manifest=finalized,
            database_committed=True,
        )
        return failure or (0, finalized)
    except Exception as exc:
        db.rollback()
        manifest.update(
            {
                "status": (
                    "applied_post_commit_processing_failed"
                    if database_committed
                    else "failed"
                ),
                "database_committed": database_committed,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "stage": (
                        "post_commit_manifest_generation"
                        if database_committed
                        else "database_preflight_or_atomic_apply"
                    ),
                },
            }
        )
        finalized = _finalize(manifest)
        failure = _write_or_fail(
            path=manifest_path,
            manifest=finalized,
            database_committed=database_committed,
        )
        return failure or ((4 if database_committed else 3), finalized)
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run or atomically apply immutable evidence lifecycle actions"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--operator",
        help="Operator identity; required for --apply and must match every action actor.",
    )
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest or default_manifest_path(args.input)
    code, manifest = run_lifecycle(
        input_path=args.input,
        manifest_path=manifest_path,
        apply=args.apply,
        operator=args.operator,
    )
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "status": manifest["status"],
                "database_committed": manifest["database_committed"],
                "manifest_sha256": manifest["manifest_sha256"],
                "changed_target_count": manifest["changed_target_count"],
                "idempotent_count": manifest["idempotent_count"],
            },
            sort_keys=True,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
