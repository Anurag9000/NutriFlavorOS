#!/usr/bin/env python3
"""Validate and optionally upsert recipe preparation evidence profiles.

The importer is intentionally offline-only. The public API exposes read and
compile operations but does not permit ordinary authenticated users to mutate
global evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List

from pydantic import TypeAdapter, ValidationError

from backend.database import SessionLocal
from backend.domain.preparation_evidence import RecipePreparationProfileInput
from backend.services.preparation_evidence_service import upsert_profiles


PROFILE_LIST = TypeAdapter(List[RecipePreparationProfileInput])


def _load(path: Path) -> List[RecipePreparationProfileInput]:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "profiles" in raw:
        raw = raw["profiles"]
    return PROFILE_LIST.validate_python(raw)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or import provenance-bearing recipe preparation profiles"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit validated profiles. Without this flag the command is a dry run.",
    )
    args = parser.parse_args()

    try:
        profiles = _load(args.input)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Preparation profile import failed validation: {exc}")
        return 2

    reviewed = sum(value.evidence_status.value == "reviewed" for value in profiles)
    print(
        json.dumps(
            {
                "input": str(args.input),
                "profile_count": len(profiles),
                "reviewed_count": reviewed,
                "dry_run": not args.apply,
                "recipe_ids": sorted(value.recipe_id for value in profiles),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not args.apply:
        return 0

    db = SessionLocal()
    try:
        values = upsert_profiles(db, profiles)
        print(f"Upserted {len(values)} preparation profiles")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Preparation profile import failed: {type(exc).__name__}: {exc}")
        return 3
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
