from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBRecipe
from backend.domain.preparation_evidence import RecipePreparationProfileInput
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.preparation_evidence_service import (
    register_profile,
    register_profiles_atomic,
)


def _payload(recipe_id: str, version: str, **updates):
    raw = {
        "recipe_id": recipe_id,
        "profile_version": version,
        "schema_version": "1",
        "supported_servings_min": 1,
        "supported_servings_max": 4,
        "task_templates": [
            {
                "template_id": "heat",
                "name": "Heat",
                "duration_min_minutes": 5,
                "duration_max_minutes": 10,
                "resource_demands": {"burner": 1},
                "dependencies": [],
                "active_work": True,
                "unattended_allowed": False,
            }
        ],
        "source_name": "Atomic import fixture",
        "source_url": f"https://example.test/{recipe_id}/{version}",
        "source_version": version,
        "evidence_status": "reviewed",
        "reviewed_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "reviewed_by": "Atomic reviewer",
        "active": True,
    }
    raw.update(updates)
    return RecipePreparationProfileInput.model_validate(raw)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = Session()
    session.add_all(
        [
            DBRecipe(
                id="recipe-a",
                name="Recipe A",
                description="",
                ingredients=["water"],
                ingredient_data=[],
                servings=2,
                calories=100,
                macros={},
                flavor_profile={},
                tags=[],
                instructions=[],
                estimated_cost=1,
                nutrition_basis="per_serving",
            ),
            DBRecipe(
                id="recipe-b",
                name="Recipe B",
                description="",
                ingredients=["water"],
                ingredient_data=[],
                servings=2,
                calories=100,
                macros={},
                flavor_profile={},
                tags=[],
                instructions=[],
                estimated_cost=1,
                nutrition_basis="per_serving",
            ),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_batch_success_commits_every_profile_together(db):
    values = register_profiles_atomic(
        db,
        [_payload("recipe-b", "1"), _payload("recipe-a", "1")],
    )
    assert [(value.recipe_id, value.profile_version) for value in values] == [
        ("recipe-a", "1"),
        ("recipe-b", "1"),
    ]
    assert db.query(DBRecipePreparationProfile).count() == 2


def test_invalid_later_row_rolls_back_earlier_insert(db):
    with pytest.raises(ValueError, match="Unknown recipe_id"):
        register_profiles_atomic(
            db,
            [_payload("recipe-a", "1"), _payload("missing", "1")],
        )
    assert db.query(DBRecipePreparationProfile).count() == 0


def test_failed_batch_rolls_back_prior_supersession_state(db):
    original = register_profile(db, _payload("recipe-a", "1"))
    with pytest.raises(ValueError, match="Unknown recipe_id"):
        register_profiles_atomic(
            db,
            [_payload("recipe-a", "2"), _payload("missing", "1")],
        )
    db.expire_all()
    rows = db.query(DBRecipePreparationProfile).all()
    assert len(rows) == 1
    assert rows[0].id == original.id
    assert rows[0].active is True
    assert rows[0].supersedes_profile_id is None


def test_batch_rejects_multiple_active_reviewed_versions_for_one_recipe(db):
    with pytest.raises(ValueError, match="at most one active reviewed version"):
        register_profiles_atomic(
            db,
            [_payload("recipe-a", "1"), _payload("recipe-a", "2")],
        )
    assert db.query(DBRecipePreparationProfile).count() == 0


def test_draft_and_one_active_reviewed_version_can_share_a_batch(db):
    values = register_profiles_atomic(
        db,
        [
            _payload(
                "recipe-a",
                "draft-1",
                evidence_status="draft",
                reviewed_at=None,
                reviewed_by=None,
                active=False,
            ),
            _payload("recipe-a", "reviewed-1"),
        ],
    )
    assert len(values) == 2
    active_reviewed = [
        value
        for value in db.query(DBRecipePreparationProfile).all()
        if value.active and value.evidence_status == "reviewed"
    ]
    assert len(active_reviewed) == 1
    assert active_reviewed[0].profile_version == "reviewed-1"
