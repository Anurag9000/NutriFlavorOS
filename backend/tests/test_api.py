from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to NutriFlavorOS API"}

def test_generate_plan_integration():
    user_payload = {
        "age": 25,
        "weight_kg": 70,
        "height_cm": 175,
        "gender": "male",
        "activity_level": 1.55,
        "goal": "maintenance",
        "liked_ingredients": ["Chicken"],
        "disliked_ingredients": [],
        "dietary_restrictions": []
    }
    
    response = client.post("/generate_plan", json=user_payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "user_id" in data
    assert len(data["days"]) == 3
    
    day1 = data["days"][0]
    assert day1["scores"]["health_match"] > 0
    assert "Breakfast" in day1["meals"]

def test_generate_plan_invalid_input():
    # Missing required field 'age'
    user_payload = {
        "weight_kg": 70,
        "height_cm": 175,
        # age missing
        "gender": "male",
        "activity_level": 1.55,
        "goal": "maintenance"
    }
    
    response = client.post("/generate_plan", json=user_payload)
    assert response.status_code == 422 # Validation Error
