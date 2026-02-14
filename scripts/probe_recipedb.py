import requests
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import APIConfig

def probe_auth():
    base = f"{APIConfig.RECIPEDB_BASE_URL}/recipe2-api/recipe/recipesinfo"
    key = APIConfig.RECIPEDB_API_KEY
    
    print(f"Probing: {base}")
    
    attempts = [
        ("Header 'x-api-key'", {}, {"x-api-key": key}),
        ("Header 'key'", {}, {"key": key}),
        ("Header 'ApiKey'", {}, {"ApiKey": key}),
        ("Header 'Authorization Bearer'", {}, {"Authorization": f"Bearer {key}"}),
        ("Query 'key'", {"key": key}, {}),
        ("Query 'api_key'", {"api_key": key}, {}),
        ("Query 'ApiKey'", {"ApiKey": key}, {}),
    ]
    
    with open("recipe_probe_results.txt", "w") as f:
        for name, params, headers in attempts:
            msg = f"\n--- {name} ---\n"
            try:
                # Add defaults
                p = {"page": 1, "limit": 1}
                p.update(params)
                
                resp = requests.get(base, params=p, headers=headers, verify=False, timeout=5)
                msg += f"Status: {resp.status_code}\n"
                msg += f"Response: {resp.text[:500]}\n"
            except Exception as e:
                msg += f"Error: {e}\n"
            
            print(msg)
            f.write(msg)

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    probe_auth()
