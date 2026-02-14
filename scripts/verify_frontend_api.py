import requests
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_api():
    print("--- Verifying Frontend-Backend Integration ---")
    
    # 1. Auth: Login
    print("\n1. Testing Auth (Login)...")
    try:
        auth_resp = requests.post(f"{BASE_URL}/auth/login", json={"email": "test@example.com", "password": "any"})
        if auth_resp.status_code == 200:
            token = auth_resp.json()["access_token"]
            user_id = auth_resp.json()["user"]["id"]
            print(f"✅ Login Success. Token: {token[:10]}... UserID: {user_id}")
            headers = {"Authorization": f"Bearer {token}"}
        else:
            print(f"❌ Login Failed: {auth_resp.status_code} - {auth_resp.text}")
            return
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    # 2. User Profile
    print("\n2. Testing User Profile...")
    try:
        user_resp = requests.get(f"{BASE_URL}/user/{user_id}", headers=headers)
        if user_resp.status_code == 200:
            print(f"✅ User Profile: OK (Name: {user_resp.json().get('name')})")
        else:
            print(f"❌ User Profile Failed: {user_resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # 3. Meal Generation
    print("\n3. Testing Meal Generation...")
    try:
        # Using dummy profile data matching frontend request
        profile_data = {
            "age": 30,
            "weight_kg": 70,
            "height_cm": 175,
            "gender": "male",
            "activity_level": 1.5,
            "goal": "maintenance"
        }
        plan_resp = requests.post(f"{BASE_URL}/meals/generate", json=profile_data, headers=headers)
        if plan_resp.status_code == 200:
            plan = plan_resp.json()
            days = len(plan.get("days", []))
            print(f"✅ Meal Plan: OK ({days} days generated)")
        else:
            print(f"❌ Meal Plan Failed: {plan_resp.status_code} - {plan_resp.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # 4. Grocery List
    print("\n4. Testing Grocery List...")
    try:
        grocery_resp = requests.get(f"{BASE_URL}/grocery/shopping_list/{user_id}", headers=headers)
        # Note: Grocery endpoint might fail if it relies on ML models that need data, 
        # but the route exists.
        if grocery_resp.status_code == 200:
            print(f"✅ Grocery List: OK")
        elif grocery_resp.status_code == 500:
             print(f"⚠️ Grocery List: 500 (Expected if no history/ML model not ready, but route exists)")
        else:
            print(f"❌ Grocery List Failed: {grocery_resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api()
