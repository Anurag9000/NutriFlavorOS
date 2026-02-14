import requests
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import APIConfig

def probe_entity():
    # Try different endpoints for "garlic"
    endpoints = [
        ("entities/by-entity-alias-readable", {"entity_alias_readable": "garlic"}),
        ("food/by-alias", {"food_pair": "garlic"}), # Pairing endpoint
        ("molecules", {"ingredient": "garlic"}) # Guess?
    ]
    
    headers = {}
    if APIConfig.FLAVORDB_API_KEY:
        headers = {"Authorization": f"Bearer {APIConfig.FLAVORDB_API_KEY}"}

    for path, params in endpoints:
        print(f"--- Probing {path} ---")
        url = f"{APIConfig.FLAVORDB_BASE_URL}/{path}"
        try:
            resp = requests.get(url, params=params, headers=headers, verify=False, timeout=5)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Keys: {data.keys() if isinstance(data, dict) else 'List/Other'}")
                # Dump first item if list
                to_dump = data
                if isinstance(data, list) and data: to_dump = data[0]
                elif isinstance(data, dict) and "content" in data: to_dump = data["content"]
                
                print(f"Sample: {json.dumps(to_dump, indent=2)[:300]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    probe_entity()
