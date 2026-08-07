"""PostgreSQL-only fixture for preparation lifecycle concurrency probes."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from backend.database import DBHousehold, DBUser, engine
from backend.schema_verification import verify_runtime_schema
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
)


def _reset_reviewed_postgres_data() -> None:
    """Clear mutable test data while preserving the Alembic-reviewed schema.

    PostgreSQL CI upgrades the database to the reviewed migration head before
    these fixtures run. Rebuilding tables from ``Base.metadata`` is unsafe here:
    migration-owned tables can legitimately exist even when they are not part of
    the currently imported ORM metadata graph, which can make ``drop_all()`` try
    to remove a referenced parent before its migration-owned child.

    Truncating all application tables keeps the exact migrated DDL, foreign keys,
    indexes, check constraints, and Alembic revision in place while still giving
    each concurrency test an empty, identity-reset database.
    """

    verify_runtime_schema()
    table_names = sorted(
        table_name
        for table_name in inspect(engine).get_table_names(schema="public")
        if table_name != "alembic_version"
    )
    if not table_names:
        return

    preparer = engine.dialect.identifier_preparer
    qualified_tables = ", ".join(
        f"{preparer.quote_schema('public')}.{preparer.quote(table_name)}"
        for table_name in table_names
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                f"TRUNCATE TABLE {qualified_tables} "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture()
def postgres_db():
    """Provide committed shared state visible to independent worker sessions."""

    assert engine.dialect.name == "postgresql", (
        "PostgreSQL preparation race fixtures must never run on SQLite"
    )
    _reset_reviewed_postgres_data()
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = Session()
    owner = DBUser(
        id=OWNER_ID,
        name="PostgreSQL Preparation Owner",
        liked_ingredients=[],
        disliked_ingredients=[],
        allergies=[],
        dietary_restrictions=[],
        health_conditions=[],
        medications=[],
    )
    household = DBHousehold(
        id=HOUSEHOLD_ID,
        owner_user_id=OWNER_ID,
        name="PostgreSQL preparation household",
        timezone="UTC",
        version=1,
    )
    session.add_all([owner, household])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        _reset_reviewed_postgres_data()


__all__ = ["postgres_db"]
