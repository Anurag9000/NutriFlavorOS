from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import preparation_routes
from backend.database import Base, DBRecipe, get_db
from backend.domain.preparation_evidence import RecipePreparationProfileInput
from backend.preparation_models import DBRecipePreparationProfile
from backend.services.preparation_evidence_service import upsert_profile
from backend.utils.security import get_current_user


def _client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        db.add(
            DBRecipe(
                id="api-soup",
                name="API soup",
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
        db.commit()
        upsert_profile(
            db,
            RecipePreparationProfileInput.model_validate(
                {
                    "recipe_id": "api-soup",
                    "supported_servings_min": 1,
                    "supported_servings_max": 4,
                    "task_templates": [
                        {
                            "template_id": "heat",
                            "name": "Heat soup",
                            "duration_min_minutes": 8,
                            "duration_max_minutes": 12,
                            "resource_demands": {"burner": 1},
                            "unattended_allowed": False,
                        }
                    ],
                    "source_name": "API fixture",
                    "source_url": "https://example.test/api-soup",
                    "source_version": "1",
                    "evidence_status": "reviewed",
                    "reviewed_at": datetime(2026, 7, 31, tzinfo=timezone.utc),
                    "reviewed_by": "API reviewer",
                }
            ),
        )

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(preparation_routes.router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user@example.test"
    )
    return TestClient(app)


def test_profile_listing_and_detail_are_provenance_complete():
    client = _client()
    listing = client.get("/api/v1/preparation/profiles")
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    detail = client.get("/api/v1/preparation/recipes/api-soup/profile")
    assert detail.status_code == 200
    body = detail.json()
    assert body["source_version"] == "1"
    assert body["reviewed_by"] == "API reviewer"
    assert body["task_templates"][0]["duration_max_minutes"] == 12


def test_build_tasks_compiles_reviewed_profile_and_rejects_uncovered_servings():
    client = _client()
    response = client.post(
        "/api/v1/preparation/build-tasks",
        json={
            "occurrences": [
                {
                    "occurrence_id": "day1.dinner",
                    "recipe_id": "api-soup",
                    "required_finish_minute": 120,
                    "servings": 2,
                },
                {
                    "occurrence_id": "day2.dinner",
                    "recipe_id": "api-soup",
                    "required_finish_minute": 300,
                    "servings": 8,
                },
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tasks"][0]["task_id"] == "day1.dinner.heat"
    assert body["tasks"][0]["duration_minutes"] == 12
    assert body["unresolved"][0]["occurrence_id"] == "day2.dinner"
    assert body["unresolved"][0]["reason_code"] == "servings_outside_reviewed_range"
