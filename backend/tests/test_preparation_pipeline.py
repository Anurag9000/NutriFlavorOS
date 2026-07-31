from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, DBRecipe
from backend.domain.preparation import PreparationResource
from backend.domain.preparation_evidence import RecipePreparationProfileInput
from backend.domain.preparation_pipeline import CompileAndScheduleRequest
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.preparation_evidence_service import upsert_profile
from backend.services.preparation_pipeline_service import compile_and_schedule


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
            id="pipeline-soup",
            name="Pipeline soup",
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
        )
    )
    session.commit()
    upsert_profile(
        session,
        RecipePreparationProfileInput.model_validate(
            {
                "recipe_id": "pipeline-soup",
                "profile_version": "1",
                "supported_servings_min": 1,
                "supported_servings_max": 4,
                "task_templates": [
                    {
                        "template_id": "chop",
                        "name": "Chop",
                        "duration_min_minutes": 5,
                        "duration_max_minutes": 10,
                        "resource_demands": {"counter": 1},
                    },
                    {
                        "template_id": "simmer",
                        "name": "Simmer",
                        "duration_min_minutes": 20,
                        "duration_max_minutes": 30,
                        "resource_demands": {"burner": 1},
                        "dependencies": ["chop"],
                    },
                ],
                "source_name": "Pipeline fixture",
                "source_url": "https://example.test/pipeline-soup",
                "source_version": "1",
                "evidence_status": "reviewed",
                "reviewed_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
                "reviewed_by": "Pipeline reviewer",
            }
        ),
    )
    try:
        yield session
    finally:
        session.close()


def request(*, allow_partial: bool = False):
    return CompileAndScheduleRequest.model_validate(
        {
            "occurrences": [
                {
                    "occurrence_id": "day1.dinner",
                    "recipe_id": "pipeline-soup",
                    "required_finish_minute": 120,
                    "servings": 2,
                    "priority": 5,
                },
                {
                    "occurrence_id": "day2.dinner",
                    "recipe_id": "missing-profile",
                    "required_finish_minute": 240,
                    "servings": 2,
                    "priority": 1,
                },
            ],
            "allow_partial": allow_partial,
            "horizon_minutes": 300,
            "granularity_minutes": 5,
            "resources": [
                {"resource_id": "counter", "capacity": 1},
                {"resource_id": "burner", "capacity": 1},
            ],
        }
    )


def test_unresolved_occurrence_blocks_schedule_by_default(db):
    result = compile_and_schedule(db, request())
    assert result.execution_status == "blocked_unresolved"
    assert result.schedule is None
    assert result.partial is False
    assert len(result.compilation.tasks) == 2
    assert result.compilation.unresolved[0].reason_code == "profile_missing"


def test_partial_schedule_requires_explicit_opt_in_and_preserves_provenance(db):
    result = compile_and_schedule(db, request(allow_partial=True))
    assert result.execution_status == "scheduled"
    assert result.partial is True
    assert result.schedule is not None
    assert [value.task_id for value in result.schedule.scheduled] == [
        "day1.dinner.chop",
        "day1.dinner.simmer",
    ]
    assert result.schedule.scheduled[1].start_minute >= result.schedule.scheduled[0].finish_minute
    diagnostics = result.schedule.diagnostics
    assert diagnostics["partial_schedule"] is True
    assert diagnostics["unresolved_occurrence_count"] == 1
    assert "sha256:" in diagnostics["profile_versions"]["pipeline-soup"]


def test_no_compilable_tasks_remains_explicit_even_when_partial_is_allowed(db):
    payload = CompileAndScheduleRequest.model_validate(
        {
            "occurrences": [
                {
                    "occurrence_id": "missing",
                    "recipe_id": "missing-profile",
                    "required_finish_minute": 60,
                    "servings": 1,
                }
            ],
            "allow_partial": True,
            "horizon_minutes": 60,
        }
    )
    result = compile_and_schedule(db, payload)
    assert result.execution_status == "no_compilable_tasks"
    assert result.schedule is None
    assert result.partial is True


def test_occurrence_deadlines_cannot_exceed_pipeline_horizon():
    with pytest.raises(ValidationError, match="deadlines exceed"):
        CompileAndScheduleRequest.model_validate(
            {
                "occurrences": [
                    {
                        "occurrence_id": "late",
                        "recipe_id": "pipeline-soup",
                        "required_finish_minute": 61,
                        "servings": 1,
                    }
                ],
                "horizon_minutes": 60,
            }
        )
