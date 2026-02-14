
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"
USER_ID = "usr_1"

def check_endpoint(name, url):
    try:
        print(f"Checking {name}...", end=" ")
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Simple check if data is not empty/zero where expected
            if isinstance(data, list) and len(data) > 0:
                print("✅ OK (List populated)")
            elif isinstance(data, dict) and (data.get("leaderboard") or data.get("carbon_saved_kg") or data.get("shopping_list")):
                 print(f"✅ OK (Dict populated: {list(data.keys())})")
            else:
                 print(f"⚠️  OK but empty/unexpected: {data}")
        else:
            print(f"❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def verify_demo():
    print("--- Verifying Demo Mode Endpoints ---")
    
    # Analytics
    check_endpoint("Health History", f"{BASE_URL}/analytics/health/{USER_ID}")
    check_endpoint("Taste Profile", f"{BASE_URL}/analytics/taste/{USER_ID}")
    check_endpoint("Variety", f"{BASE_URL}/analytics/variety/{USER_ID}")
    
    # Sustainability
    check_endpoint("Sustainability Metrics", f"{BASE_URL}/sustainability/{USER_ID}")
    check_endpoint("Carbon Footprint", f"{BASE_URL}/sustainability/carbon-footprint/{USER_ID}")
    
    # Grocery
    check_endpoint("Shopping List", f"{BASE_URL}/grocery/shopping_list/{USER_ID}")
    check_endpoint("Next Purchase", f"{BASE_URL}/grocery/predict/{USER_ID}/Avocados")
    
    # Gamification
    check_endpoint("Achievements", f"{BASE_URL}/gamification/achievements/{USER_ID}")
    check_endpoint("Leaderboard", f"{BASE_URL}/gamification/leaderboard")
    check_endpoint("Impact Summary", f"{BASE_URL}/gamification/impact_summary/{USER_ID}")

if __name__ == "__main__":
    verify_demo()
