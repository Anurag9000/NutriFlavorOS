
import os
import requests
from dotenv import load_dotenv

# Load the newly created .env
load_dotenv()

api_key = os.getenv("RECIPEDB_API_KEY")
base_url = os.getenv("RECIPEDB_BASE_URL")
mock_mode = os.getenv("MOCK_MODE")

print(f"Loaded Config: URL={base_url}, Key={'Present' if api_key else 'Missing'}, Mock={mock_mode}")

if not api_key:
    print("FATAL: API Key not found in .env")
    exit(1)

# Test Real API Call
test_url = f"{base_url}/recipe/recipeofday"
headers = {"Authorization": f"Bearer {api_key}"}

print(f"Testing Connectivity to: {test_url}")
try:
    response = requests.get(test_url, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS: Real API is accessible and authenticated!")
        print(f"Sample Data: {response.text[:100]}...")
    else:
        print(f"FAILED: API returned {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"ERROR: Connection failed - {e}")
