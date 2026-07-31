from __future__ import annotations

import io
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app


client = TestClient(app)


def _create_account() -> tuple[str, str]:
    email = f"contract-{uuid4().hex}@example.test"
    password = "correct-horse-battery-staple"
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "name": "Contract Test"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["user"]["id"] == email
    assert payload["user"]["profile_complete"] is False
    assert payload["user"]["missing_profile_fields"]
    return email, payload["access_token"]


def test_signup_and_login_contract() -> None:
    email, signup_token = _create_account()
    assert signup_token

    response = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


def test_taste_feedback_requires_authentication_and_never_mutates_models() -> None:
    email, token = _create_account()
    payload = {
        "user_id": email,
        "recipe_id": "rec_123",
        "rating": 0.8,
        "user_genome": [0.1] * 32,
        "recipe_profile": [0.2] * 32,
    }

    unauthenticated = client.post("/api/v1/feedback/taste", json=payload)
    assert unauthenticated.status_code == 401

    response = client.post(
        "/api/v1/feedback/taste",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202, response.text
    result = response.json()
    assert result["status"] == "accepted"
    assert result["model_updated"] is False
    assert result["event_id"] > 0


def test_vision_endpoint_is_authenticated_and_explicitly_disabled() -> None:
    _, token = _create_account()
    image = Image.new("RGB", (32, 32), color="red")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="JPEG")
    image_bytes.seek(0)

    unauthenticated = client.post(
        "/api/v1/vision/analyze",
        files={"image": ("test.jpg", image_bytes.getvalue(), "image/jpeg")},
    )
    assert unauthenticated.status_code == 401

    response = client.post(
        "/api/v1/vision/analyze",
        files={"image": ("test.jpg", image_bytes.getvalue(), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 501, response.text
    assert "validated checkpoint" in response.json()["detail"].lower()
