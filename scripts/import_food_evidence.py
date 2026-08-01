#!/usr/bin/env python3
"""Validate and atomically import immutable conversion and storage evidence."""

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
from backend.domain.evidence_import import FoodEvidenceImportDocument
from backend.services.evidence_import_service import (
    EvidenceImportPreview,
    preflight_food_evidence,
    register_food_evidence_atomic,
)


IMPORTER_VERSION = "immutable-food-evidence-import-v1"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> FoodEvidenceImportDocument:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    return FoodEvidenceImportDocument.model_validate(raw)


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
    return input_path.with_suffix(input_path.suffix + ".import-manifest.json")


def _base_manifest(
    *,
    input_path: Path,
    input_hash: str | None,
    operator: str | None,
    apply: bool,
) -> dict:
    return {
        "protocol_version": "immutable_food_evidence_import_manifest_v1",
        "importer_version": IMPORTER_VERSION,
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
        "conversion_count": 0,
        "storage_policy_count": 0,
        "reviewer_identities": [],
        "rows": [],
        "status": "started",
        "atomic": True,
        "database_committed": False,
        "inserted_count": 0,
        "idempotent_count": 0,
        "error": None,
        "limitations": [
            "Manifest hashing detects later modification but does not authenticate the source publisher.",
            "Dry-run preflight does not reserve natural keys against future concurrent imports.",
            "Reviewed conversion and storage evidence remains conditional on its declared source and scope.",
            "Storage-policy evidence is not a universal food-safety guarantee.",
        ],
    }


def _reviewers(document: FoodEvidenceImportDocument) -> list[str]:
    values = {
        value.reviewed_by.strip()
        for value in [
            *document.conversion_versions,
            *document.storage_policy_versions,
        ]
        if value.reviewed_by and value.reviewed_by.strip()
    }
    return sorted(values)


def _preview_rows(previews: list[EvidenceImportPreview]) -> list[dict]:
    return [value.to_dict() for value in previews]


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


def run_import(
    *,
    input_path: Path,
    manifest_path: Path,
    apply: bool,
    operator: str | None,
) -> tuple[int, dict]:
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

    manifest.update(
        {
            "document_version": document.document_version,
            "conversion_count": len(document.conversion_versions),
            "storage_policy_count": len(document.storage_policy_versions),
            "reviewer_identities": _reviewers(document),
        }
    )
    db = SessionLocal()
    try:
        manifest["database_dialect"] = db.get_bind().dialect.name
        previews = preflight_food_evidence(
            db,
            document.conversion_versions,
            document.storage_policy_versions,
        )
        manifest["rows"] = _preview_rows(previews)
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

        result = register_food_evidence_atomic(
            db,
            document.conversion_versions,
            document.storage_policy_versions,
        )
        conversion_by_version = {
            (
                value.canonical_name,
                value.from_unit,
                value.to_unit,
                value.record_version,
            ): value
            for value in result.conversions
        }
        policy_by_version = {
            (value.policy_key, value.policy_version): value
            for value in result.storage_policies
        }
        final_rows = []
        for preview in result.previews:
            row = preview.to_dict()
            if preview.evidence_kind == "conversion":
                canonical_name, from_unit, to_unit = preview.natural_key.split("|", 2)
                value = conversion_by_version[
                    (canonical_name, from_unit, to_unit, preview.record_version)
                ]
                row.update(
                    {
                        "record_id": value.id,
                        "result_active": value.active,
                        "result_supersedes_record_id": value.supersedes_conversion_id,
                    }
                )
            else:
                value = policy_by_version[
                    (preview.natural_key, preview.record_version)
                ]
                row.update(
                    {
                        "record_id": value.id,
                        "result_active": value.active,
                        "result_supersedes_record_id": value.supersedes_policy_id,
                    }
                )
            row["outcome"] = (
                "idempotent_existing"
                if preview.planned_action == "idempotent_existing"
                else "registered"
            )
            final_rows.append(row)

        manifest.update(
            {
                "rows": final_rows,
                "status": "applied",
                "database_committed": True,
                "inserted_count": result.inserted_count,
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
                "status": "failed",
                "database_committed": False,
                "inserted_count": 0,
                "idempotent_count": 0,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "stage": "database_preflight_or_atomic_apply",
                },
            }
        )
        finalized = _finalize(manifest)
        failure = _write_or_fail(
            path=manifest_path,
            manifest=finalized,
            database_committed=False,
        )
        return failure or (3, finalized)
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or atomically import immutable food evidence"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the complete validated document as one transaction.",
    )
    parser.add_argument(
        "--operator",
        help="Person or controlled process performing the import; required with --apply.",
    )
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest or default_manifest_path(args.input)
    code, manifest = run_import(
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
                "inserted_count": manifest["inserted_count"],
                "idempotent_count": manifest["idempotent_count"],
            },
            sort_keys=True,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
