from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import evidence_history_routes
from backend.database import Base, DBHousehold, DBRecipe, DBUser, get_db
from backend.domain.inventory import LeftoverCreate
from backend.services.inventory_service_v4 import create_leftover
from backend.services.official_evidence_history import seed_official_storage_policy_versions
from backend.utils.security import get_current_user


def _client() -> tuple[TestClient, int]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        owner = DBUser(
            id="owner@example.test",
            name="Owner",
            liked_ingredients=[],
            disliked_ingredients=[],
            allergies=[],
            dietary_restrictions=[],
            health_conditions=[],
            medications=[],
        )
        household = DBHousehold(
            id="evidence-home",
            owner_user_id=owner.id,
            name="Evidence home",
            timezone="UTC",
            version=1,
        )
        other = DBHousehold(
            id="other-home",
            owner_user_id=owner.id,
            name="Other home",
            timezone="UTC",
            version=1,
        )
        recipe = DBRecipe(
            id="api-pizza",
            name="Pizza",
            description="",
            ingredients=["pizza"],
            ingredient_data=[],
            servings=2,
            calories=400,
            macros={},
            flavor_profile={},
            tags=[],
            instructions=[],
            estimated_cost=5,
            nutrition_basis="per_serving",
        )
        db.add_all([owner, household, other, recipe])
        db.commit()
        seed_official_storage_policy_versions(db)
        leftover = create_leftover(
            db,
            household,
            LeftoverCreate(
                recipe_id=recipe.id,
                portions_available=2,
                cooked_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                frozen=False,
                storage_policy_key="pizza_refrigerated",
                idempotency_key="api-leftover-evidence-0001",
            ),
        )
        leftover_id = leftover.id

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(evidence_history_routes.router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="owner@example.test"
    )
    return TestClient(app), leftover_id


def test_owner_can_read_exact_leftover_policy_version():
    client, leftover_id = _client()
    response = client.get(
        f"/api/v1/food-evidence/history/households/evidence-home/leftovers/{leftover_id}/storage-policy"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["policy_key"] == "pizza_refrigerated"
    assert body["policy_version"] == "official-2026-07-31"
    assert body["reviewed_by"]
    assert len(body["content_hash"]) == 64


def test_leftover_cannot_be_read_through_a_different_household_path():
    client, leftover_id = _client()
    response = client.get(
        f"/api/v1/food-evidence/history/households/other-home/leftovers/{leftover_id}/storage-policy"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Resource not found"


def test_inaccessible_household_is_not_disclosed():
    client, leftover_id = _client()
    client.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="outsider@example.test"
    )
    response = client.get(
        f"/api/v1/food-evidence/history/households/evidence-home/leftovers/{leftover_id}/storage-policy"
    )
    assert response.status_code == 404
