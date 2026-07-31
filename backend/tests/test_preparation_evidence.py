from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBRecipe
from backend.domain.preparation_evidence import (
    BuildPreparationTasksRequest,
    DurationPolicy,
    PreparationEvidenceStatus,
    RecipePreparationOccurrence,
    RecipePreparationProfileInput,
)
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.preparation_evidence_service import (
    build_tasks_from_profiles,
    get_profile,
    list_profiles,
    profile_content_hash,
    upsert_profile,
    upsert_profiles,
)


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
    session.add(
        DBRecipe(
            id="reviewed-soup",
            name="Reviewed soup",
            description="",
            ingredients=["water"],
            ingredient_data=[],
            servings=4,
            calories=100,
            macros={},
            flavor_profile={},
            tags=[],
            instructions=[],
            estimated_cost=1,
            nutrition_basis="per_serving",
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def reviewed_profile(**updates):
    raw = {
        "recipe_id": "reviewed-soup",
        "profile_version": "1",
        "schema_version": "1",
        "supported_servings_min": 2,
        "supported_servings_max": 6,
        "task_templates": [
            {
                "template_id": "chop",
                "name": "Chop ingredients",
                "duration_min_minutes": 10,
                "duration_max_minutes": 15,
                "resource_demands": {"counter": 1},
                "dependencies": [],
                "active_work": True,
                "unattended_allowed": False,
            },
            {
                "template_id": "simmer",
                "name": "Simmer",
                "duration_min_minutes": 25,
                "duration_max_minutes": 35,
                "resource_demands": {"burner": 1},
                "dependencies": ["chop"],
                "active_work": False,
                "unattended_allowed": None,
            },
        ],
        "source_name": "Reviewed kitchen protocol",
        "source_url": "https://example.test/reviewed-soup",
        "source_version": "2026-07",
        "evidence_status": "reviewed",
        "reviewed_at": "2026-07-31T00:00:00Z",
        "reviewed_by": "Kitchen evidence reviewer",
        "active": True,
    }
    raw.update(updates)
    return RecipePreparationProfileInput.model_validate(raw)


def test_reviewed_profile_requires_review_metadata_timezone_and_acyclic_templates():
    with pytest.raises(ValidationError, match="reviewed_at"):
        reviewed_profile(reviewed_at=None)
    with pytest.raises(ValidationError, match="timezone"):
        reviewed_profile(reviewed_at="2026-07-31T00:00:00")
    value = reviewed_profile(reviewed_at="2026-07-31T05:30:00+05:30")
    assert value.reviewed_at == datetime(2026, 7, 31, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="dependency cycle"):
        reviewed_profile(
            task_templates=[
                {
                    "template_id": "a",
                    "name": "A",
                    "duration_min_minutes": 1,
                    "duration_max_minutes": 1,
                    "dependencies": ["b"],
                },
                {
                    "template_id": "b",
                    "name": "B",
                    "duration_min_minutes": 1,
                    "duration_max_minutes": 1,
                    "dependencies": ["a"],
                },
            ]
        )


def test_identical_version_retry_is_idempotent_and_hash_stable(db):
    payload = reviewed_profile()
    first = upsert_profile(db, payload)
    repeated = upsert_profile(db, payload)
    assert repeated.id == first.id
    assert repeated.content_hash == first.content_hash == profile_content_hash(payload)
    assert len(first.content_hash) == 64
    assert db.query(DBRecipePreparationProfile).count() == 1


def test_contradictory_reuse_of_profile_version_is_rejected(db):
    upsert_profile(db, reviewed_profile())
    with pytest.raises(ValueError, match="different evidence content"):
        upsert_profile(
            db,
            reviewed_profile(
                task_templates=[
                    {
                        "template_id": "changed",
                        "name": "Changed task",
                        "duration_min_minutes": 20,
                        "duration_max_minutes": 25,
                    }
                ]
            ),
        )
    assert db.query(DBRecipePreparationProfile).count() == 1


def test_new_reviewed_version_supersedes_prior_active_version(db):
    first = upsert_profile(db, reviewed_profile())
    second = upsert_profile(
        db,
        reviewed_profile(
            profile_version="2",
            source_version="2026-08",
            notes="Reviewed revision",
        ),
    )
    db.expire_all()
    old_row = db.get(DBRecipePreparationProfile, first.id)
    new_row = db.get(DBRecipePreparationProfile, second.id)
    assert old_row.active is False
    assert new_row.active is True
    assert new_row.supersedes_profile_id == old_row.id
    assert get_profile(db, "reviewed-soup").id == new_row.id
    assert len(list_profiles(db)) == 1
    assert len(list_profiles(db, active_only=False)) == 2


def test_batch_import_rejects_duplicate_natural_keys(db):
    with pytest.raises(ValueError, match="duplicate recipe_id/profile_version"):
        upsert_profiles(db, [reviewed_profile(), reviewed_profile()])


def test_compiler_namespaces_dependencies_and_embeds_evidence_provenance(db):
    profile = upsert_profile(db, reviewed_profile())
    result = build_tasks_from_profiles(
        db,
        BuildPreparationTasksRequest(
            occurrences=[
                RecipePreparationOccurrence(
                    occurrence_id="day1.dinner",
                    recipe_id="reviewed-soup",
                    required_finish_minute=120,
                    servings=4,
                    priority=3,
                )
            ]
        ),
    )

    assert result.unresolved == []
    assert [(task.task_id, task.duration_minutes) for task in result.tasks] == [
        ("day1.dinner.chop", 15),
        ("day1.dinner.simmer", 35),
    ]
    assert result.tasks[1].dependencies == ["day1.dinner.chop"]
    assert result.tasks[1].latest_finish_minute == 120
    metadata = result.tasks[1].metadata
    assert metadata["source_version"] == "2026-07"
    assert metadata["profile_version"] == "1"
    assert metadata["profile_content_hash"] == profile.content_hash
    assert metadata["unattended_allowed"] is None
    assert profile.content_hash in result.profile_versions["reviewed-soup"]
    assert result.warnings


def test_optimistic_duration_policy_is_disclosed(db):
    upsert_profile(db, reviewed_profile())
    result = build_tasks_from_profiles(
        db,
        BuildPreparationTasksRequest(
            occurrences=[
                RecipePreparationOccurrence(
                    occurrence_id="day1.dinner",
                    recipe_id="reviewed-soup",
                    required_finish_minute=120,
                    servings=4,
                )
            ],
            duration_policy=DurationPolicy.OPTIMISTIC_MIN,
        ),
    )
    assert [task.duration_minutes for task in result.tasks] == [10, 25]
    assert "Optimistic minimum durations" in result.warnings[0]


def test_missing_unreviewed_inactive_and_serving_mismatch_are_unresolved(db):
    upsert_profile(
        db,
        reviewed_profile(
            profile_version="draft-1",
            evidence_status="draft",
            reviewed_at=None,
            reviewed_by=None,
        ),
    )
    result = build_tasks_from_profiles(
        db,
        BuildPreparationTasksRequest(
            occurrences=[
                RecipePreparationOccurrence(
                    occurrence_id="draft",
                    recipe_id="reviewed-soup",
                    required_finish_minute=120,
                    servings=4,
                ),
                RecipePreparationOccurrence(
                    occurrence_id="missing",
                    recipe_id="no-profile",
                    required_finish_minute=120,
                    servings=1,
                ),
            ]
        ),
    )
    assert {value.reason_code for value in result.unresolved} == {
        "profile_not_reviewed",
        "profile_missing",
    }

    upsert_profile(db, reviewed_profile(profile_version="reviewed-1"))
    outside = build_tasks_from_profiles(
        db,
        BuildPreparationTasksRequest(
            occurrences=[
                RecipePreparationOccurrence(
                    occurrence_id="too-many",
                    recipe_id="reviewed-soup",
                    required_finish_minute=120,
                    servings=8,
                )
            ]
        ),
    )
    assert outside.unresolved[0].reason_code == "servings_outside_reviewed_range"


def test_upsert_rejects_unknown_recipe(db):
    with pytest.raises(ValueError, match="Unknown recipe_id"):
        upsert_profile(
            db,
            reviewed_profile(recipe_id="unknown-recipe"),
        )
