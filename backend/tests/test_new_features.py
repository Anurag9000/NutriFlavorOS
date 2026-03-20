import pytest
from fastapi.testclient import TestClient
from backend.main import app
import json
import io
from PIL import Image

client = TestClient(app)

def test_signup_and_login():
    # Test Signup
    signup_data = {"email": "test@foodscope.ai", "password": "securepassword", "name": "Test User"}
    response = client.post("/api/v1/auth/signup", json=signup_data)
    if response.status_code == 400 and "already exists" in response.text.lower():
        print("User already exists, proceeding to login.")
    else:
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    # Test Login (OAuth2 form data)
    login_data = {"username": "test@foodscope.ai", "password": "securepassword"}
    response = client.post("/api/v1/auth/token", data=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]
    return token

def test_online_learning_taste():
    # We don't need auth for this endpoint currently, but we test the payload
    payload = {
        "user_id": "test@foodscope.ai",
        "recipe_id": "rec_123",
        "rating": 0.8,
        "user_genome": [0.1] * 512,
        "recipe_profile": [0.2] * 512
    }
    response = client.post("/api/v1/feedback/taste", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_vision_endpoint():
    # Create a dummy image
    img = Image.new('RGB', (224, 224), color = 'red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    
    response = client.post(
        "/api/v1/vision/analyze",
        files={"image": ("test.jpg", img_byte_arr, "image/jpeg")}
    )
    if response.status_code != 200:
        print(f"DEBUG: Vision Response Status: {response.status_code}")
        print(f"DEBUG: Vision Response Body: {response.text}")
        raise Exception(f"Vision endpoint failed with status {response.status_code}: {response.text}")
    
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] == True
    assert "calories" in res_json["data"]

if __name__ == "__main__":
    print("Running Tests...")
    try:
        tok = test_signup_and_login()
        print("Auth OK. Token:", tok[:10] + "...")
        test_online_learning_taste()
        print("Online Learning OK.")
        test_vision_endpoint()
        print("Vision Endpoint OK.")
        print("ALL TESTS PASSED.")
    except Exception as e:
        print(f"TEST FAILED: {e}")
