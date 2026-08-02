"""PostgreSQL-only fixture for preparation lifecycle concurrency probes."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from backend.database import Base, DBHousehold, DBUser, engine
from backend.tests.test_preparation_operations_service import (
    HOUSEHOLD_ID,
    OWNER_ID,
)


@pytest.fixture()
def postgres_db():
    """Provide committed shared state visible to independent worker sessions."""

    assert engine.dialect.name == "postgresql", (
        "PostgreSQL preparation race fixtures must never run on SQLite"
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
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
        Base.metadata.drop_all(engine)


__all__ = ["postgres_db"]
