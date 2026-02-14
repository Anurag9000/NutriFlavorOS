import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import APIConfig
from backend.services.flavordb_service import FlavorDBService

def verify_flavordb():
    print("--- FLAVORDB VERIFICATION START ---")
    f_service = FlavorDBService()
    try:
        print(f"Testing URL: {f_service.base_url}")
        print("Searching for 'Garlic'...")
        res = f_service.search_by_common_name("Garlic")
        if res:
             print("SUCCESS: search_by_common_name returned data")
             if isinstance(res, dict):
                 print(f"Keys: {list(res.keys())}")
             print(f"Data Sample: {str(res)[:100]}")
        else:
             print("WARNING: search_by_common_name returned empty")
             
    except Exception as e:
        print(f"FAILURE: FlavorDB Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- FLAVORDB VERIFICATION END ---")

if __name__ == "__main__":
    verify_flavordb()
