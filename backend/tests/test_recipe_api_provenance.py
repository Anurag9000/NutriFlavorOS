from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import recipe_routes
from backend.database import Base, DBRecipe, get_db


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
                id="provenance-recipe",
                name="Reviewed oats",
                description="Measured fixture",
                ingredients=["1/2 cup rolled oats"],
                ingredient_data=[
                    {
                        "raw": "1/2 cup rolled oats",
                        "name": "rolled oats",
                        "quantity_min": 0.5,
                        "quantity_max": 0.5,
                        "unit": "cup",
                        "canonical_quantity_min": 118.29411825,
                        "canonical_quantity_max": 118.29411825,
                        "canonical_unit": "ml",
                        "parse_status": "normalized",
                    }
                ],
                servings=2,
                calories=320,
                macros={"protein": 12, "carbs": 55, "fat": 7},
                flavor_profile={"sweet": 0.2},
                tags=["breakfast"],
                cuisine="international",
                instructions=["Combine ingredients."],
                estimated_cost=2.5,
                source_name="Reviewed fixture source",
                source_url="https://example.test/recipe",
                source_version="2026-07",
                nutrition_basis="per_recipe",
            )
        )
        db.commit()

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(recipe_routes.router)
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_recipe_detail_preserves_canonical_quantity_and_source_fields():
    response = _client().get("/api/v1/recipes/provenance-recipe")
    assert response.status_code == 200
    recipe = response.json()
    assert recipe["servings"] == 2
    assert recipe["nutrition_basis"] == "per_recipe"
    assert recipe["source_name"] == "Reviewed fixture source"
    assert recipe["source_url"] == "https://example.test/recipe"
    assert recipe["source_version"] == "2026-07"
    assert recipe["ingredient_lines"][0]["canonical_unit"] == "ml"
    assert recipe["ingredient_lines"][0]["canonical_quantity_min"] == 118.29411825


def test_recipe_search_uses_same_complete_mapping():
    response = _client().get("/api/v1/recipes/search?q=oats")
    assert response.status_code == 200
    values = response.json()
    assert len(values) == 1
    assert values[0]["ingredient_lines"][0]["name"] == "rolled oats"
    assert values[0]["source_version"] == "2026-07"
