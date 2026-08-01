"""Deployment-time database schema verification.

Hosted instances must run the exact reviewed Alembic revision before serving
requests. Table-presence checks alone cannot detect missing constraints, indexes,
or column semantics from later migrations.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from backend.database import REQUIRED_RUNTIME_TABLES, engine


CURRENT_ALEMBIC_REVISION = "20260801_0011"
CURRENT_REQUIRED_TABLES = REQUIRED_RUNTIME_TABLES | {
    "recipe_preparation_profiles",
    "ingredient_conversion_versions",
    "storage_policy_versions",
    "leftover_storage_policy_evidence",
    "evidence_lifecycle_events",
    "resource_calendar_versions",
    "household_preparation_resources",
    "persisted_preparation_schedules",
    "preparation_schedule_events",
}


def verify_runtime_schema(
    bind: Engine = engine,
    *,
    expected_revision: str = CURRENT_ALEMBIC_REVISION,
    required_tables: Iterable[str] = CURRENT_REQUIRED_TABLES,
) -> None:
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    missing = set(required_tables) - tables
    if missing:
        raise RuntimeError(
            "Database schema is incomplete; run `alembic upgrade head`. "
            f"Missing tables: {', '.join(sorted(missing))}"
        )
    if "alembic_version" not in tables:
        raise RuntimeError(
            "Database has no Alembic revision record; run `alembic upgrade head` "
            "instead of relying on ORM table creation"
        )
    with bind.connect() as connection:
        revisions = [
            str(row[0])
            for row in connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            ).fetchall()
        ]
    if revisions != [expected_revision]:
        observed = ", ".join(revisions) if revisions else "none"
        raise RuntimeError(
            "Database migration revision mismatch; run `alembic upgrade head`. "
            f"Expected {expected_revision}; observed {observed}"
        )
