import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.sustainablefooddb_service import SustainableFoodDBService
from backend.services.dietrxdb_service import DietRxDBService
from backend.services.recipedb_service import RecipeDBService
from backend.config import APIConfig
import urllib3
urllib3.disable_warnings()

def verify_fallback():
    print("=== VERIFYING API FALLBACK MECHANISM ===")
    
    # 1. Verify SustainableDB Fallback (Current Key Fails -> Should return Mock)
    print("\n--- Testing SustainableDB Fallback (Expect Mock Data) ---")
    s = SustainableFoodDBService()
    # Force URL to be reachable but likely fail auth
    # Or strict check: The service should catch the 400/401 and return mock.
    
    try:
        res = s.search_sustainable_foods("Tomato")
        print(f"Result Type: {type(res)}")
        if res and isinstance(res, list) and len(res) > 0:
            item = res[0]
            print(f"Sample Item: {item}")
            # Check if it looks like mock data
            # Mock data has "carbon_footprint_kg" usually?
            # My mock implementation in BaseAPIService returns list of dicts.
            if "carbon_footprint_kg" in str(item) or "rating" in str(item):
                 print("SUCCESS: Returned data (likely Mock if live failed).")
            else:
                 print("Result received but might be live?")
        else:
            print("WARNING: Returned empty list (Fallback might have failed to find match or Mock DB is empty for 'Tomato')")
            
    except Exception as e:
        print(f"FAILURE: Exception leaked through! {e}")

    # 2. Verify DietRx Fallback
    print("\n--- Testing DietRxDB Fallback (Expect Mock Data) ---")
    d = DietRxDBService()
    try:
        res = d.get_disease_info("Flu")
        print(f"Result: {str(res)[:100]}")
        if res and "description" in res: # Mock DB usually has description
            print("SUCCESS: Returned data.")
        else:
            print("WARNING: Empty result.")
    except Exception as e:
        print(f"FAILURE: Exception leaked through! {e}")

    # 3. Simulate Connection Error (Bad URL)
    print("\n--- Testing Forced Connection Error (Bad URL) ---")
    # 3. Simulate Connection Error (Bad URL)
    print("\n--- Testing Forced Connection Error (Bad URL) ---")
    # Hack: Temporarily break URL in instance but keep "sustainable" keyword
    s.base_url = "http://sustainable-invalid-url.com"
    try:
        res = s.search_sustainable_foods("Tomato")
        print(f"Result from Bad URL: {str(res)[:100]}")
        if res:
            print("SUCCESS: Fallback activated on Connection Error.")
        else:
            print("WARNING: Empty result on connection error.")
    except Exception as e:
        print(f"FAILURE: Exception leaked through on Bad URL! {e}")

if __name__ == "__main__":
    verify_fallback()
