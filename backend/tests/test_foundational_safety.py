import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import auth_routes
from backend.database import Base, get_db
from backend.engines.plan_generator import InfeasiblePlanError, PlanGenerator
from backend.models import Gender, Goal, Recipe, UserProfile


@pytest.fixture()
def auth_client(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-longer-than-thirty-two-characters")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(auth_routes.router)
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_signup_hashes_password_and_login_rejects_wrong_password(auth_client):
    signup = auth_client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Test User",
            "email": "USER@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert signup.status_code == 201
    assert signup.json()["user"]["email"] == "user@example.com"
    assert signup.json()["access_token"] != "demo_token_123"

    wrong = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "not-the-password"},
    )
    assert wrong.status_code == 401

    correct = auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert correct.status_code == 200
    assert correct.json()["user"]["id"] == "user@example.com"


def test_signup_rejects_duplicate_email(auth_client):
    payload = {
        "name": "Test User",
        "email": "duplicate@example.com",
        "password": "correct horse battery staple",
    }
    assert auth_client.post("/api/v1/auth/signup", json=payload).status_code == 201
    assert auth_client.post("/api/v1/auth/signup", json=payload).status_code == 409


def _profile(**updates):
    values = {
        "name": "Planner Test",
        "age": 30,
        "weight_kg": 70,
        "height_cm": 170,
        "gender": Gender.OTHER,
        "activity_level": 1.4,
        "goal": Goal.MAINTENANCE,
    }
    values.update(updates)
    return UserProfile(**values)


def _recipe(recipe_id: str, name: str, ingredients):
    return Recipe(
        id=recipe_id,
        name=name,
        description="",
        ingredients=ingredients,
        calories=300,
        macros={"protein": 20, "carbs": 30, "fat": 10},
    )


def test_keyword_filter_uses_word_boundaries():
    assert PlanGenerator._contains_term("ham sandwich", "ham")
    assert not PlanGenerator._contains_term("chamomile tea", "ham")
    assert PlanGenerator._contains_term("roasted peanuts", "peanut")


def test_planner_fails_closed_when_all_recipes_violate_constraints():
    planner = PlanGenerator.__new__(PlanGenerator)
    planner.recipes = [_recipe("1", "Chicken bowl", ["chicken", "rice"])]

    with pytest.raises(InfeasiblePlanError):
        planner._filter_valid_recipes(_profile(dietary_restrictions=["vegan"]))


def test_user_profile_mutable_defaults_are_isolated():
    first = _profile()
    second = _profile()
    first.allergies.append("peanut")
    assert second.allergies == []
