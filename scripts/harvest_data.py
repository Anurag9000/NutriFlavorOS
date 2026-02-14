import os
import json
import time
import requests
import sys

# Add parent dir to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import APIConfig

# Output Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "data")
RECIPES_FILE = os.path.join(DATA_DIR, "recipes.json")
FLAVOR_FILE = os.path.join(DATA_DIR, "flavor_db.json")

# Configuration
RECIPE_LIMIT = 50  # Fetch 50 recipes
DELAY = 0.5 # Delay between requests to be polite

def fetch_recipes():
    print(f"--- Harvesting RecipeDB ({RECIPE_LIMIT} items) ---")
    url = f"{APIConfig.RECIPEDB_BASE_URL}/recipe2-api/recipe/recipesinfo"
    
    all_recipes = []
    page = 1
    limit = 10 
    
    while len(all_recipes) < RECIPE_LIMIT:
        print(f"Fetching Page {page}...")
        try:
            # Correct Auth: Bearer Token
            headers = {"Authorization": f"Bearer {APIConfig.RECIPEDB_API_KEY}"}
            
            resp = requests.get(url, params={"page": page, "limit": limit}, headers=headers, verify=False, timeout=10)
            if resp.status_code != 200:
                print(f"Failed to fetch page {page}: {resp.status_code}")
                # print(resp.text[:500])
                break
                
            data = resp.json()
            
            # Debug: Print keys to understand structure
            if page == 1: print(f"Response Keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}") 
            
            # Unwrap Payload
            if isinstance(data, dict) and "payload" in data: 
                data = data["payload"]

            # Unwrap Response
            if isinstance(data, dict) and "response" in data:
                data = data["response"]

            # Find List
            recipes_list = []
            if isinstance(data, list):
                recipes_list = data
            elif isinstance(data, dict):
                if "recipes" in data:
                    recipes_list = data["recipes"]
                elif "data" in data:
                    recipes_list = data["data"]
            
            if not recipes_list:
                print(f"No recipes found in page {page}. Data keys: {data.keys() if isinstance(data, dict) else 'List empty'}")
                break
                
            print(f"  > Found {len(recipes_list)} recipes.")
            all_recipes.extend(recipes_list)
            page += 1
            time.sleep(DELAY)
            
        except Exception as e:
            print(f"Error fetching recipes: {e}")
            break
            
    # Trim to limit
    all_recipes = all_recipes[:RECIPE_LIMIT]
    print(f"Fetched {len(all_recipes)} recipes.")
    
    # Save
    with open(RECIPES_FILE, 'w') as f:
        json.dump(all_recipes, f, indent=2)
    print(f"Saved to {RECIPES_FILE}")
    return all_recipes

def fetch_flavors(recipes):
    print("\n--- Harvesting FlavorDB (Ingredients from Recipes) ---")
    
    # 1. Extract Ingredients
    ingredients = set()
    for r in recipes:
        # Check standard RecipeDB keys for ingredients
        # Usually "ingredients" list or parsed from "instructions"?
        # RecipeDB v2 usually has 'ingredients' key listing objects
        if "ingredients" in r:
             for i in r["ingredients"]:
                 # i might be a string or dict
                 if isinstance(i, dict):
                     ingredients.add(i.get("name", "").lower())
                 elif isinstance(i, str):
                     ingredients.add(i.lower())
    
    # Also add some known staples if missing
    staples = ["garlic", "onion", "chicken", "tomato", "beef", "salt", "pepper", "rice", "honey"]
    ingredients.update(staples)
    
    # Remove empty
    ingredients = {i for i in ingredients if i and len(i) > 2}
    print(f"Found {len(ingredients)} unique ingredients to query.")
    
    # 2. Query FlavorDB
    flavor_db = {}
    
    # Load existing if available (to merge, or just overwrite? User said 'download all', implying refresh)
    # But let's overwrite to ensure it's 'Real' data only.
    
    url = f"{APIConfig.FLAVORDB_BASE_URL}/molecules_data/by-commonName"
    
    for idx, ing in enumerate(ingredients):
        if idx >= 100: # Safety cap for this run
            print("Reached safety cap of 100 ingredients.")
            break
            
        print(f"[{idx+1}/{len(ingredients)}] Fetching: {ing}...")
        try:
            # Note: API Key in params or header? 
            # Config says: FLAVORDB_API_KEY. BaseService puts it in Authorization Bearer usually.
            headers = {}
            if APIConfig.FLAVORDB_API_KEY:
                headers = {"Authorization": f"Bearer {APIConfig.FLAVORDB_API_KEY}"}

            resp = requests.get(url, params={"common_name": ing}, headers=headers, verify=False, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                # FlavorDB structure: {"content": [...]} 
                if isinstance(data, dict) and "content" in data and len(data["content"]) > 0:
                    item = data["content"][0] # Take first match
                    
                    # Store in our simplified format
                    flavor_db[ing] = {
                        "ingredient": ing,
                        "category": item.get("category", "other"),
                        "flavor_profile": item.get("flavor_profile", {}),
                        "functional_groups": item.get("functional_groups", []),
                        "molecular_properties": item.get("molecular_properties", {}),
                        "natural_occurrence": item.get("natural", False),
                        # Keep raw item data too if needed? No, simplfied for our mock DB schema
                        "safety_approvals": {
                             "fema": bool(item.get("fema_number")),
                             "jecfa": False, # Unavailable in this endpoint usually
                             "efsa": False
                        }
                    }
                else:
                    # Not found
                    # print(f"  > No data found for {ing}")
                    pass
            else:
                print(f"  > Error {resp.status_code}")
                
            time.sleep(DELAY)
            
        except Exception as e:
            print(f"  > Exception: {e}")
            
    print(f"Fetched details for {len(flavor_db)} ingredients.")
    
    # Save
    with open(FLAVOR_FILE, 'w') as f:
        json.dump(flavor_db, f, indent=2)
    print(f"Saved to {FLAVOR_FILE}")

def main():
    print("STARTING DATA HARVEST...")
    import urllib3
    urllib3.disable_warnings()
    
    recipes = fetch_recipes()
    if recipes:
        fetch_flavors(recipes)
    
    print("\nHARVEST COMPLETE.")

if __name__ == "__main__":
    main()
