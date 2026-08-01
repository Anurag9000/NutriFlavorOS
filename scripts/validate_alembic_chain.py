#!/usr/bin/env python3
"""Validate that every Alembic revision forms one complete reviewed chain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory

from backend.schema_verification import CURRENT_ALEMBIC_REVISION


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_ROOT = ROOT / "backend" / "migrations"
VERSION_ROOT = MIGRATION_ROOT / "versions"


def _config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATION_ROOT))
    return config


def _render_down_revision(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return [str(value)]


def validate_alembic_chain() -> dict[str, Any]:
    errors: list[str] = []
    script = ScriptDirectory.from_config(_config())
    heads = sorted(script.get_heads())
    bases = sorted(script.get_bases())

    if heads != [CURRENT_ALEMBIC_REVISION]:
        errors.append(
            "Alembic head mismatch: expected "
            f"[{CURRENT_ALEMBIC_REVISION!r}]; observed {heads}"
        )
    if len(bases) != 1:
        errors.append(f"Alembic chain must have exactly one base; observed {bases}")

    try:
        revisions = list(script.walk_revisions(base="base", head="heads"))
    except Exception as exc:  # Alembic emits several branch-resolution types.
        revisions = []
        errors.append(f"Alembic revision walk failed: {type(exc).__name__}: {exc}")

    revision_ids = [value.revision for value in revisions]
    if len(revision_ids) != len(set(revision_ids)):
        errors.append("Alembic revision IDs are not unique")

    edges: list[dict[str, Any]] = []
    for value in revisions:
        down = _render_down_revision(value.down_revision)
        edges.append(
            {
                "revision": value.revision,
                "down_revisions": down,
                "dependencies": _render_down_revision(value.dependencies),
                "path": str(Path(value.path).resolve().relative_to(ROOT)),
            }
        )
        if len(down) > 1:
            errors.append(
                f"Merge revision is prohibited in the direct-main linear chain: {value.revision} -> {down}"
            )
        if value.dependencies:
            errors.append(
                f"Alembic dependency edges are prohibited in the linear chain: {value.revision}"
            )

    children: dict[str, list[str]] = {}
    for value in revisions:
        for parent in _render_down_revision(value.down_revision):
            children.setdefault(parent, []).append(value.revision)
    forks = {
        parent: sorted(values)
        for parent, values in children.items()
        if len(values) > 1
    }
    if forks:
        errors.append(
            "Alembic chain contains forked children: "
            + "; ".join(
                f"{parent} -> {values}" for parent, values in sorted(forks.items())
            )
        )

    linear_chain: list[str] = []
    if len(heads) == 1:
        seen: set[str] = set()
        current = script.get_revision(heads[0])
        while current is not None:
            if current.revision in seen:
                errors.append(f"Alembic cycle detected at revision {current.revision}")
                break
            seen.add(current.revision)
            linear_chain.append(current.revision)
            down = _render_down_revision(current.down_revision)
            if not down:
                break
            if len(down) != 1:
                break
            current = script.get_revision(down[0])
        linear_chain.reverse()
        if set(linear_chain) != set(revision_ids):
            missing = sorted(set(revision_ids) - set(linear_chain))
            extra = sorted(set(linear_chain) - set(revision_ids))
            errors.append(
                "Alembic head-to-base chain does not cover every revision; "
                f"missing={missing}, extra={extra}"
            )

    migration_files = sorted(
        path
        for path in VERSION_ROOT.glob("*.py")
        if path.name != "__init__.py"
    )
    revision_paths = {Path(value.path).resolve() for value in revisions}
    orphan_files = [
        str(path.relative_to(ROOT))
        for path in migration_files
        if path.resolve() not in revision_paths
    ]
    missing_files = [
        str(Path(value.path).resolve().relative_to(ROOT))
        for value in revisions
        if not Path(value.path).is_file()
    ]
    if orphan_files:
        errors.append(
            "Migration files are not represented in the Alembic chain: "
            + ", ".join(orphan_files)
        )
    if missing_files:
        errors.append(
            "Alembic revisions reference missing files: " + ", ".join(missing_files)
        )

    filename_mismatches = []
    for value in revisions:
        name = Path(value.path).name
        if not name.startswith(f"{value.revision}_"):
            filename_mismatches.append(
                {
                    "revision": value.revision,
                    "path": str(Path(value.path).resolve().relative_to(ROOT)),
                }
            )
    if filename_mismatches:
        errors.append(
            "Migration filenames must begin with their revision ID: "
            + ", ".join(
                f"{value['revision']}={value['path']}" for value in filename_mismatches
            )
        )

    return {
        "valid": not errors,
        "expected_head": CURRENT_ALEMBIC_REVISION,
        "heads": heads,
        "bases": bases,
        "linear_chain": linear_chain,
        "revision_count": len(revisions),
        "migration_file_count": len(migration_files),
        "edges": sorted(edges, key=lambda value: value["revision"]),
        "forks": forks,
        "orphan_files": orphan_files,
        "missing_files": missing_files,
        "filename_mismatches": filename_mismatches,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the complete Alembic chain")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = validate_alembic_chain()
    except (OSError, TypeError, ValueError) as exc:
        print(f"Alembic chain validation failed: {type(exc).__name__}: {exc}")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
