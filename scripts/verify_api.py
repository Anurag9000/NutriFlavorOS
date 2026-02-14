import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import APIConfig
from backend.services.recipedb_service import RecipeDBService
from backend.services.flavordb_service import FlavorDBService

def verify_api():
    print("--- API VERIFICATION START ---")
    
    # RecipeDB
    print("\n[RecipeDB]")
    r_service = RecipeDBService()
    try:
        rod = r_service.get_recipe_of_day()
        if rod:
            print("SUCCESS: get_recipe_of_day returned data")
            if isinstance(rod, dict):
                print(f"Keys: {list(rod.keys())}")
                if "title" in rod:
                    print(f"Title: {rod['title']}")
                if "instructions" in rod:
                     print(f"Instructions type: {type(rod['instructions'])}")
            else:
                 print(f"Type: {type(rod)}")
        else:
            print("WARNING: get_recipe_of_day returned empty/None")
            
    except Exception as e:
        print(f"FAILURE: RecipeDB Error: {e}")

    print("\n--- RECIPEDB LIST CHECK (Strict Params) ---")
    try:
        print("Fetching recipes list (limit=5)...")
        r_list = r_service.get_recipes_list(page=1, limit=5)
        # Check if it wraps content in 'recipes' or is a direct list?
        # Postman response snippet 527 showed: response is list? "[ { ... } ]" (Line 44) but that's "response" array in Postman meta.
        # rdb2_postman_collection.json: "response": [ ... ]
        # The logic in _make_request unwraps 'payload' then 'data'. 
        # If the API returns { payload: { data: [...] } }, we get [...].
        if isinstance(r_list, list):
            print(f"SUCCESS: Fetched {len(r_list)} recipes.")
            if r_list:
                print(f"Sample Item Keys: {list(r_list[0].keys())[:5]}")
        elif isinstance(r_list, dict):
             print(f"SUCCESS (Dict): Keys: {list(r_list.keys())}")
        else:
             print(f"WARNING: Unexpected type {type(r_list)}")
    except Exception as e:
        print(f"FAILURE: RecipeDB List Error: {e}")

    # FlavorDB
    print("\n[FlavorDB]")
    f_service = FlavorDBService()
    try:
        # Check basic connectivity with a common ingredient
        print("Searching for 'Garlic'...")
        # Note: FlavorDB endpoints might need update too, checking existing
        # existing: by-flavorProfile?ingredient=Garlic
        # Postman: {{baseUrl}}/recipe2-api/recipe/recipe-day/with-ingredients-categories ? No that's RecipeDB.
        # FlavorDB Postman: {{baseUrl}}/properties/by-commonName?name=Garlic
        # flavordb_service has search_by_common_name mapping to "by-commonName"
        # If config is clean (https://cosylab.iiitd.edu.in/flavordb/), then it calls https://cosylab.iiitd.edu.in/flavordb/by-commonName
        res = f_service.search_by_common_name("Garlic")
        if res:
             print("SUCCESS: search_by_common_name returned data")
             if isinstance(res, dict):
                 print(f"Keys: {list(res.keys())[:5]}...")
                 val_sample = list(res.values())[0] if len(res)>0 else "Empty"
                 print(f"Sample value type: {type(val_sample)}")
        else:
             print("WARNING: search_by_common_name returned empty")
             
    except Exception as e:
        print(f"FAILURE: FlavorDB Error: {e}")

    print("\n--- API VERIFICATION END ---")

if __name__ == "__main__":
    verify_api()
