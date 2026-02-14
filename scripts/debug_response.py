import requests
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import APIConfig

def debug_response():
    url = f"{APIConfig.RECIPEDB_BASE_URL}/recipe2-api/recipe/recipesinfo"
    headers = {"x-api-key": APIConfig.RECIPEDB_API_KEY}
    params = {"page": 1, "limit": 5}
    
    print(f"Requesting: {url}")
    try:
        resp = requests.get(url, params=params, headers=headers, verify=False, timeout=10)
        print(f"Status: {resp.status_code}")
        
        data = resp.json()
        
        # Dump to file
        with open("recipe_debug.json", "w") as f:
            json.dump(data, f, indent=2)
            
        print("Response dumped to recipe_debug.json")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    debug_response()
