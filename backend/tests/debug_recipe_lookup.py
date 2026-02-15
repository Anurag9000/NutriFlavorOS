
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.recipedb_service import RecipeDBService
from backend.config import APIConfig

def test_lookup():
    print(f"MOCK_MODE: {APIConfig.MOCK_MODE}")
    print(f"Recipes File: {APIConfig.MOCK_RECIPES_FILE}")
    
    # Force Mock Mode just in case
    APIConfig.MOCK_MODE = True
    
    service = RecipeDBService()
    
    # Test 1: Lookup 'rec_01' (Oatmeal)
    print("\n--- Testing 'rec_01' ---")
    result = service.get_recipe_info("rec_01")
    if result:
        print("✅ Found 'rec_01':")
        print(f"Name: {result.get('name')}")
        print(f"ID: {result.get('id')}")
    else:
        print("❌ 'rec_01' NOT FOUND")

    # Test 2: Lookup '2613' (Falafel)
    print("\n--- Testing '2613' ---")
    result = service.get_recipe_info("2613")
    if result:
        print("✅ Found '2613':")
        print(f"Name: {result.get('name')}")
    else:
        print("❌ '2613' NOT FOUND")
        
    # Test 3: List all IDs in mock DB to verify
    print("\n--- Checking Mock DB IDs ---")
    try:
        with open(APIConfig.MOCK_RECIPES_FILE, 'r') as f:
            data = json.load(f)
            ids = [str(r.get("Recipe_id")) for r in data[-25:]] # Last 25
            print(f"Total Content Length: {len(data)}")
            print(f"Last 25 IDs: {ids}")
    except Exception as e:
        print(f"Error reading file manually: {e}")

if __name__ == "__main__":
    test_lookup()
