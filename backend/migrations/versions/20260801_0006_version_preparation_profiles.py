"""Version, hash, and supersede preparation evidence profiles.

Revision ID: 20260801_0006
Revises: 20260731_0005
Create Date: 2026-08-01
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260801_0006"
down_revision: Union[str, None] = "20260731_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {
        value["name"]
        for value in sa.inspect(op.get_bind()).get_columns(table)
    }


def _unique_constraints(table: str) -> set[str]:
    return {
        value["name"]
        for value in sa.inspect(op.get_bind()).get_unique_constraints(table)
        if value.get("name")
    }


def _indexes(table: str) -> set[str]:
    return {
        value["name"]
        for value in sa.inspect(op.get_bind()).get_indexes(table)
        if value.get("name")
    }


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text_value = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text_value)
        except ValueError:
            return text_value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _content_hash(row: sa.RowMapping) -> str:
    canonical = {
        "recipe_id": row["recipe_id"],
        "profile_version": "1",
        "schema_version": row["schema_version"],
        "supported_servings_min": row["supported_servings_min"],
        "supported_servings_max": row["supported_servings_max"],
        "task_templates": _json_value(row["task_templates"]),
        "source_name": row["source_name"],
        "source_url": row["source_url"],
        "source_version": row["source_version"],
        "evidence_status": row["evidence_status"],
        "reviewed_at": _iso(row["reviewed_at"]),
        "reviewed_by": row["reviewed_by"],
        "notes": row["notes"],
    }
    raw = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def upgrade() -> None:
    table = "recipe_preparation_profiles"
    if table not in _tables():
        raise RuntimeError(
            "recipe_preparation_profiles is missing; apply revision 20260731_0005 first"
        )

    existing = _columns(table)
    with op.batch_alter_table(table) as batch:
        if "profile_version" not in existing:
            batch.add_column(
                sa.Column(
                    "profile_version",
                    sa.String(),
                    nullable=True,
                    server_default="1",
                )
            )
        if "content_hash" not in existing:
            batch.add_column(sa.Column("content_hash", sa.String(64), nullable=True))
        if "supersedes_profile_id" not in existing:
            batch.add_column(
                sa.Column("supersedes_profile_id", sa.Integer(), nullable=True)
            )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, recipe_id, schema_version, supported_servings_min, "
            "supported_servings_max, task_templates, source_name, source_url, "
            "source_version, evidence_status, reviewed_at, reviewed_by, notes "
            "FROM recipe_preparation_profiles"
        )
    ).mappings().all()
    for row in rows:
        bind.execute(
            sa.text(
                "UPDATE recipe_preparation_profiles "
                "SET profile_version = COALESCE(profile_version, '1'), "
                "content_hash = :content_hash WHERE id = :id"
            ),
            {"content_hash": _content_hash(row), "id": row["id"]},
        )

    null_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM recipe_preparation_profiles "
            "WHERE profile_version IS NULL OR profile_version = '' "
            "OR content_hash IS NULL OR content_hash = ''"
        )
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            "Preparation profile version/hash backfill was incomplete"
        )

    uniques = _unique_constraints(table)
    with op.batch_alter_table(table) as batch:
        batch.alter_column(
            "profile_version",
            existing_type=sa.String(),
            nullable=False,
            server_default=None,
        )
        batch.alter_column(
            "content_hash",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        if "uq_recipe_preparation_profile_recipe" in uniques:
            batch.drop_constraint(
                "uq_recipe_preparation_profile_recipe",
                type_="unique",
            )
        if "uq_recipe_preparation_profile_version" not in uniques:
            batch.create_unique_constraint(
                "uq_recipe_preparation_profile_version",
                ["recipe_id", "profile_version"],
            )
        batch.create_check_constraint(
            "ck_recipe_preparation_profile_version_nonempty",
            "profile_version <> ''",
        )
        batch.create_foreign_key(
            "fk_recipe_preparation_profile_supersedes",
            table,
            ["supersedes_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )

    indexes = _indexes(table)
    if "ix_recipe_preparation_profiles_content_hash" not in indexes:
        op.create_index(
            "ix_recipe_preparation_profiles_content_hash",
            table,
            ["content_hash"],
        )
    if "ix_recipe_preparation_profiles_supersedes_profile_id" not in indexes:
        op.create_index(
            "ix_recipe_preparation_profiles_supersedes_profile_id",
            table,
            ["supersedes_profile_id"],
        )
    if "uq_active_reviewed_preparation_profile_recipe" not in indexes:
        op.create_index(
            "uq_active_reviewed_preparation_profile_recipe",
            table,
            ["recipe_id"],
            unique=True,
            sqlite_where=sa.text(
                "active = 1 AND evidence_status = 'reviewed'"
            ),
            postgresql_where=sa.text(
                "active AND evidence_status = 'reviewed'"
            ),
        )


def downgrade() -> None:
    table = "recipe_preparation_profiles"
    if table not in _tables():
        return
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT recipe_id, COUNT(*) FROM recipe_preparation_profiles "
            "GROUP BY recipe_id HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        raise RuntimeError(
            "Cannot downgrade preparation profile versioning while multiple "
            "versions exist for a recipe"
        )

    indexes = _indexes(table)
    for name in (
        "uq_active_reviewed_preparation_profile_recipe",
        "ix_recipe_preparation_profiles_content_hash",
        "ix_recipe_preparation_profiles_supersedes_profile_id",
    ):
        if name in indexes:
            op.drop_index(name, table_name=table)

    uniques = _unique_constraints(table)
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(
            "fk_recipe_preparation_profile_supersedes",
            type_="foreignkey",
        )
        batch.drop_constraint(
            "ck_recipe_preparation_profile_version_nonempty",
            type_="check",
        )
        if "uq_recipe_preparation_profile_version" in uniques:
            batch.drop_constraint(
                "uq_recipe_preparation_profile_version",
                type_="unique",
            )
        batch.create_unique_constraint(
            "uq_recipe_preparation_profile_recipe",
            ["recipe_id"],
        )
        batch.drop_column("supersedes_profile_id")
        batch.drop_column("content_hash")
        batch.drop_column("profile_version")
